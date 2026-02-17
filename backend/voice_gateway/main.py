import base64
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, status

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
    signature, ts = sign_payload(payload, settings.VOICE_GATEWAY_TO_SVONTAI_SECRET)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            url,
            params=payload,
            headers={
                "X-Voice-Signature": signature,
                "X-Voice-Timestamp": str(ts),
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _svontai_post_voice_event(event: dict) -> None:
    url = f"{_normalize_base_url(settings.SVONTAI_BACKEND_URL)}{settings.SVONTAI_VOICE_INGEST_PATH}"
    signature, ts = sign_payload(event, settings.VOICE_GATEWAY_TO_SVONTAI_SECRET)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json=event,
            headers={
                "X-Voice-Signature": signature,
                "X-Voice-Timestamp": str(ts),
            },
        )
        resp.raise_for_status()


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

    # Create a websocket URL for Twilio Media Streams
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

    return Response(content=twiml, media_type="application/xml")


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

