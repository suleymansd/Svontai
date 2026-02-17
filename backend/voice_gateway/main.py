import base64
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import PlainTextResponse

from voice_gateway.config import settings
from voice_gateway.security import sign_payload
from voice_gateway.providers.base import InboundCallRequest
from voice_gateway.providers.twilio import TwilioAdapter

logger = logging.getLogger(__name__)

app = FastAPI(title="SvontAI Voice Gateway", version="0.1.0")


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


async def _svontai_get_resolve_tenant(to_number: str) -> dict:
    url = f"{_normalize_base_url(settings.SVONTAI_BACKEND_URL)}{settings.SVONTAI_TELEPHONY_RESOLVE_PATH}"
    payload = {"to": to_number}
    signature, ts, body_str = sign_payload(payload, settings.VOICE_GATEWAY_TO_SVONTAI_SECRET)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            content=body_str,
            headers={
                "X-Voice-Signature": signature,
                "X-Voice-Timestamp": str(ts),
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _svontai_post_voice_event(event: dict) -> None:
    url = f"{_normalize_base_url(settings.SVONTAI_BACKEND_URL)}{settings.SVONTAI_VOICE_INGEST_PATH}"
    signature, ts, body_str = sign_payload(event, settings.VOICE_GATEWAY_TO_SVONTAI_SECRET)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            content=body_str,
            headers={
                "X-Voice-Signature": signature,
                "X-Voice-Timestamp": str(ts),
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()

async def _svontai_post_voice_intent(intent_payload: dict) -> dict:
    url = f"{_normalize_base_url(settings.SVONTAI_BACKEND_URL)}{settings.SVONTAI_VOICE_INTENT_PATH}"
    signature, ts, body_str = sign_payload(intent_payload, settings.VOICE_GATEWAY_TO_SVONTAI_SECRET)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            content=body_str,
            headers={
                "X-Voice-Signature": signature,
                "X-Voice-Timestamp": str(ts),
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/twilio/voice/inbound")
async def twilio_inbound_voice(request: Request) -> Response:
    """
    Twilio Voice webhook (inbound call).

    Configure in Twilio console:
      - A Voice webhook URL -> https://<VOICE_GATEWAY_PUBLIC_URL>/twilio/voice/inbound
    """
    form = await request.form()
    to_number = str(form.get("To") or "").strip()
    from_number = str(form.get("From") or "").strip()
    call_sid = str(form.get("CallSid") or "").strip()

    if not to_number or not call_sid:
        return Response("Bad Request", status_code=status.HTTP_400_BAD_REQUEST)

    resolved = await _svontai_get_resolve_tenant(to_number)
    tenant_id = resolved.get("tenantId")
    if not tenant_id:
        return Response("Tenant not resolved", status_code=status.HTTP_404_NOT_FOUND)

    # Emit call started event to SvontAI (async best-effort)
    now = datetime.now(timezone.utc).isoformat()
    await _svontai_post_voice_event(
        {
            "tenantId": str(tenant_id),
            "eventType": "voice_call_started",
            "eventId": f"twilio:{call_sid}:started",
            "from": f"tel:{from_number}",
            "to": f"tel:{to_number}",
            "timestamp": now,
            "call": {
                "provider": "twilio",
                "provider_call_id": call_sid,
                "direction": "inbound",
                "status": "started",
                "started_at": now,
            },
        }
    )

    # Default: gather loop mode (production-friendly)
    if (settings.TWILIO_VOICE_MODE or "gather").strip().lower() == "gather":
        action_url = f"/twilio/voice/intent?tenantId={tenant_id}&callSid={call_sid}&from={from_number}&to={to_number}&turn=1"
        status_cb = f"/twilio/voice/status?tenantId={tenant_id}&callSid={call_sid}&from={from_number}&to={to_number}"
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Filiz">Merhaba. Size nasıl yardımcı olabilirim?</Say>
  <Gather input="speech" language="tr-TR" speechTimeout="auto" action="{action_url}" method="POST" />
  <Say voice="Polly.Filiz">Yanıt alamadım. Tekrar dener misiniz?</Say>
  <Gather input="speech" language="tr-TR" speechTimeout="auto" action="{action_url}" method="POST" />
  <Hangup />
</Response>"""
        # Twilio status callback config is done in console; we keep endpoint for it.
        return Response(content=twiml, media_type="application/xml")

    # Fallback: stream mode (kept for later realtime pipeline)
    public_url = _normalize_base_url(settings.VOICE_GATEWAY_PUBLIC_URL)
    ws_url = public_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = f"{ws_url}/ws/twilio/media?tenantId={tenant_id}&callSid={call_sid}"
    adapter = TwilioAdapter()
    twiml = await adapter.build_connect_stream_response(
        tenant_id=str(tenant_id),
        request=InboundCallRequest(
            provider="twilio",
            to_number=to_number,
            from_number=from_number,
            provider_call_id=call_sid,
            raw={k: str(v) for k, v in form.items()},
        ),
        ws_url=ws_url,
    )
    return Response(content=twiml, media_type="application/xml")


@app.post("/twilio/voice/intent")
async def twilio_voice_intent(request: Request) -> Response:
    """
    Twilio <Gather input="speech"> action handler.
    """
    params = request.query_params
    tenant_id = params.get("tenantId", "")
    call_sid = params.get("callSid", "")
    turn = int(params.get("turn", "1") or "1")
    from_number = params.get("from", "")
    to_number = params.get("to", "")

    form = await request.form()
    speech = str(form.get("SpeechResult") or "").strip()

    if not tenant_id or not call_sid:
        return PlainTextResponse("Bad Request", status_code=status.HTTP_400_BAD_REQUEST)

    if not speech:
        # reprompt
        next_turn = turn + 1
        action_url = f"/twilio/voice/intent?tenantId={tenant_id}&callSid={call_sid}&from={from_number}&to={to_number}&turn={next_turn}"
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Filiz">Sizi duyamadım. Tekrar eder misiniz?</Say>
  <Gather input="speech" language="tr-TR" speechTimeout="auto" action="{action_url}" method="POST" />
  <Hangup />
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    intent_payload = {
        "tenantId": str(tenant_id),
        "eventType": "voice_call_intent",
        "eventId": f"twilio:{call_sid}:turn:{turn}",
        "call": {
            "provider": "twilio",
            "provider_call_id": call_sid,
            "direction": "inbound",
            "status": "in_progress",
        },
        "from": f"tel:{from_number}",
        "to": f"tel:{to_number}",
        "text": speech,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {"turn": turn},
    }

    try:
        result = await _svontai_post_voice_intent(intent_payload)
    except Exception as exc:
        logger.warning("Voice intent backend error: %s", exc, exc_info=True)
        result = {"responseText": "Şu anda teknik bir sorun yaşıyoruz. Lütfen daha sonra tekrar deneyin.", "endCall": True}

    response_text = str(result.get("responseText") or result.get("response_text") or "Anladım. Devam edelim.").strip()
    end_call = bool(result.get("endCall") or result.get("end_call") or False)

    if end_call:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Filiz">{response_text}</Say>
  <Hangup />
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    next_turn = turn + 1
    action_url = f"/twilio/voice/intent?tenantId={tenant_id}&callSid={call_sid}&from={from_number}&to={to_number}&turn={next_turn}"
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Filiz">{response_text}</Say>
  <Gather input="speech" language="tr-TR" speechTimeout="auto" action="{action_url}" method="POST" />
  <Hangup />
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/twilio/voice/status")
async def twilio_voice_status(request: Request) -> Response:
    """
    Optional Twilio status callback handler.
    """
    params = request.query_params
    tenant_id = params.get("tenantId", "")
    call_sid = params.get("callSid", "")
    from_number = params.get("from", "")
    to_number = params.get("to", "")

    form = await request.form()
    call_status = str(form.get("CallStatus") or "").strip()
    call_duration = str(form.get("CallDuration") or "").strip()

    try:
        duration_seconds = int(call_duration) if call_duration else 0
    except Exception:
        duration_seconds = 0

    if tenant_id and call_sid and call_status in {"completed", "busy", "no-answer", "failed", "canceled"}:
        now = datetime.now(timezone.utc).isoformat()
        await _svontai_post_voice_event(
            {
                "tenantId": str(tenant_id),
                "eventType": "voice_call_completed",
                "eventId": f"twilio:{call_sid}:status:{call_status}",
                "from": f"tel:{from_number}",
                "to": f"tel:{to_number}",
                "timestamp": now,
                "call": {
                    "provider": "twilio",
                    "provider_call_id": call_sid,
                    "direction": "inbound",
                    "status": call_status,
                    "ended_at": now,
                    "duration_seconds": duration_seconds,
                },
            }
        )

    return PlainTextResponse("OK")


@app.websocket("/ws/twilio/media")
async def twilio_media_ws(ws: WebSocket) -> None:
    await ws.accept()

    tenant_id = ws.query_params.get("tenantId", "")
    call_sid = ws.query_params.get("callSid", "")
    started_at = datetime.now(timezone.utc)

    audio_bytes = 0
    try:
        while True:
            msg = await ws.receive_json()
            event = msg.get("event")
            if event == "media":
                payload = (((msg.get("media") or {}).get("payload")) or "").strip()
                if payload:
                    try:
                        audio_bytes += len(base64.b64decode(payload))
                    except Exception:
                        pass
            elif event == "stop":
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Twilio WS error: %s", exc, exc_info=True)
    finally:
        ended_at = datetime.now(timezone.utc)
        duration_seconds = int(max(0, (ended_at - started_at).total_seconds()))

        if tenant_id and call_sid:
            now = ended_at.isoformat()
            try:
                await _svontai_post_voice_event(
                    {
                        "tenantId": str(tenant_id),
                        "eventType": "voice_call_completed",
                        "eventId": f"twilio:{call_sid}:completed",
                        "from": "tel:unknown",
                        "to": "tel:unknown",
                        "timestamp": now,
                        "call": {
                            "provider": "twilio",
                            "provider_call_id": call_sid,
                            "direction": "inbound",
                            "status": "completed",
                            "ended_at": now,
                            "duration_seconds": duration_seconds,
                            "meta": {"audio_bytes": audio_bytes},
                        },
                    }
                )
            except Exception as exc:
                logger.warning("Failed to post call_completed: %s", exc, exc_info=True)
