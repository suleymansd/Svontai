import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import PlainTextResponse

from voice_gateway.config import settings
from voice_gateway.security import (
    sign_payload,
    sign_websocket_session,
    verify_twilio_webhook_signature,
    verify_websocket_session,
)
from voice_gateway.providers.base import InboundCallRequest
from voice_gateway.providers.twilio import TwilioAdapter
from voice_gateway.twiml import say as _twilio_say
from voice_gateway.twiml import gather as _twilio_gather
from voice_gateway.twiml import normalize_spoken_text
from voice_gateway.twiml import xml_attr as _xml_attr
from voice_gateway.twiml import xml_text as _xml_text

logger = logging.getLogger(__name__)

app = FastAPI(title="SvontAI Voice Gateway", version="0.1.0")

RELAY_MODE = "conversation_relay"


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def _voice_intent_action_url(
    *,
    tenant_id: str,
    call_sid: str,
    from_number: str,
    to_number: str,
    turn: int,
) -> str:
    query = urlencode(
        {
            "tenantId": str(tenant_id).strip(),
            "callSid": str(call_sid).strip(),
            "from": str(from_number).strip(),
            "to": str(to_number).strip(),
            "turn": turn,
        },
        quote_via=quote,
    )
    return f"/twilio/voice/intent?{query}"


def _relay_session_payload(
    *,
    tenant_id: str,
    call_sid: str,
    from_number: str,
    to_number: str,
    direction: str,
) -> dict[str, str]:
    return {
        "tenant_id": str(tenant_id).strip(),
        "call_sid": str(call_sid).strip(),
        "from": str(from_number).strip(),
        "to": str(to_number).strip(),
        "direction": str(direction).strip(),
    }


def _conversation_relay_ws_url(**session: str) -> str:
    payload = _relay_session_payload(**session)
    signature, timestamp = sign_websocket_session(
        payload,
        settings.VOICE_GATEWAY_TO_SVONTAI_SECRET,
    )
    public_url = _normalize_base_url(settings.VOICE_GATEWAY_PUBLIC_URL)
    ws_base = public_url.replace("https://", "wss://").replace("http://", "ws://")
    query = urlencode({**payload, "ts": timestamp, "sig": signature}, quote_via=quote)
    return f"{ws_base}/ws/twilio/conversation?{query}"


def _conversation_relay_twiml(
    *,
    tenant_id: str,
    call_sid: str,
    from_number: str,
    to_number: str,
    direction: str,
) -> str:
    ws_url = _conversation_relay_ws_url(
        tenant_id=tenant_id,
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
        direction=direction,
    )
    greeting = (
        "Merhaba, ben işletmenin dijital asistanıyım. Nasıl yardımcı olabilirim?"
        if direction == "inbound"
        else "Merhaba, ben işletmenin dijital asistanıyım. Uygunsanız kısaca görüşebilir miyiz?"
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <ConversationRelay url="{_xml_attr(ws_url)}"
      welcomeGreeting="{_xml_attr(greeting)}"
      welcomeGreetingInterruptible="speech"
      language="tr-TR"
      ttsProvider="{_xml_attr(settings.TWILIO_RELAY_TTS_PROVIDER)}"
      voice="{_xml_attr(settings.TWILIO_RELAY_TTS_VOICE)}"
      transcriptionProvider="{_xml_attr(settings.TWILIO_RELAY_TRANSCRIPTION_PROVIDER)}"
      speechModel="{_xml_attr(settings.TWILIO_RELAY_SPEECH_MODEL)}"
      speechTimeout="{int(settings.TWILIO_RELAY_SPEECH_TIMEOUT_MS)}"
      interruptible="speech"
      interruptSensitivity="{_xml_attr(settings.TWILIO_RELAY_INTERRUPT_SENSITIVITY)}"
      reportInputDuringAgentSpeech="speech"
      preemptible="true"
      hints="{_xml_attr(settings.TWILIO_SPEECH_HINTS)}"
      events="speaker-events tokens-played" />
  </Connect>
  <Hangup />
</Response>"""


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


def _twilio_public_request_url(request: Request) -> str:
    base = _normalize_base_url(settings.VOICE_GATEWAY_PUBLIC_URL)
    query = request.url.query
    return f"{base}{request.url.path}{f'?{query}' if query else ''}"


def _twilio_public_websocket_url(ws: WebSocket) -> str:
    base = _normalize_base_url(settings.VOICE_GATEWAY_PUBLIC_URL)
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    query = ws.url.query
    return f"{ws_base}{ws.url.path}{f'?{query}' if query else ''}"


def _require_twilio_signature(request: Request, form: Any) -> None:
    items = [(str(key), str(value)) for key, value in form.multi_items()]
    if not verify_twilio_webhook_signature(
        _twilio_public_request_url(request),
        items,
        request.headers.get("X-Twilio-Signature", ""),
        settings.TWILIO_AUTH_TOKEN,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")


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
    _require_twilio_signature(request, form)
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

    voice_mode = (settings.TWILIO_VOICE_MODE or "gather").strip().lower()
    if voice_mode == RELAY_MODE:
        return Response(
            content=_conversation_relay_twiml(
                tenant_id=str(tenant_id),
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number,
                direction="inbound",
            ),
            media_type="application/xml",
        )

    # Gather remains the safe fallback when ConversationRelay is not enabled on the Twilio account.
    if voice_mode == "gather":
        action_url = _voice_intent_action_url(
            tenant_id=str(tenant_id),
            call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            turn=1,
        )
        status_cb = f"/twilio/voice/status?tenantId={tenant_id}&callSid={call_sid}&from={from_number}&to={to_number}"
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  {_twilio_gather("Merhaba, ben işletmenin dijital asistanıyım. Nasıl yardımcı olabilirim?", action_url)}
  {_twilio_gather("Sizi duyamadım. Bir kez daha söyler misiniz?", action_url)}
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


@app.post("/twilio/voice/outbound")
async def twilio_outbound_voice(request: Request) -> Response:
    """
    Twilio Voice webhook for outbound calls created by the SmartWA worker.

    The worker creates the call with:
      https://<VOICE_GATEWAY_PUBLIC_URL>/twilio/voice/outbound?tenantId=<tenant>&jobId=<job>
    """
    params = request.query_params
    tenant_id = params.get("tenantId", "")
    job_id = params.get("jobId", "")
    form = await request.form()
    _require_twilio_signature(request, form)
    to_number = str(form.get("To") or "").strip()
    from_number = str(form.get("From") or "").strip()
    call_sid = str(form.get("CallSid") or "").strip()

    if not tenant_id or not call_sid:
        return PlainTextResponse("Bad Request", status_code=status.HTTP_400_BAD_REQUEST)

    now = datetime.now(timezone.utc).isoformat()
    await _svontai_post_voice_event(
        {
            "tenantId": str(tenant_id),
            "eventType": "voice_call_started",
            "eventId": f"twilio:{call_sid}:outbound:started",
            "from": f"tel:{from_number}",
            "to": f"tel:{to_number}",
            "timestamp": now,
            "call": {
                "provider": "twilio",
                "provider_call_id": call_sid,
                "direction": "outbound",
                "status": "started",
                "started_at": now,
            },
            "metadata": {"outbound_job_id": job_id},
        }
    )

    if (settings.TWILIO_VOICE_MODE or "gather").strip().lower() == RELAY_MODE:
        return Response(
            content=_conversation_relay_twiml(
                tenant_id=tenant_id,
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number,
                direction="outbound",
            ),
            media_type="application/xml",
        )

    action_url = _voice_intent_action_url(
        tenant_id=tenant_id,
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
        turn=1,
    )
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  {_twilio_gather("Merhaba, ben işletmenin dijital asistanıyım. Uygunsanız kısaca görüşebilir miyiz?", action_url)}
  {_twilio_say("Yanıt alamadım. Daha sonra tekrar deneyebiliriz.")}
  <Hangup />
</Response>"""
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
    _require_twilio_signature(request, form)
    speech = str(form.get("SpeechResult") or "").strip()

    if not tenant_id or not call_sid:
        return PlainTextResponse("Bad Request", status_code=status.HTTP_400_BAD_REQUEST)

    if not speech:
        # reprompt
        next_turn = turn + 1
        action_url = _voice_intent_action_url(
            tenant_id=tenant_id,
            call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            turn=next_turn,
        )
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  {_twilio_gather("Sizi duyamadım. Bir kez daha söyler misiniz?", action_url)}
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
  {_twilio_say(response_text)}
  <Hangup />
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    next_turn = turn + 1
    action_url = _voice_intent_action_url(
        tenant_id=tenant_id,
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
        turn=next_turn,
    )
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  {_twilio_gather(response_text, action_url)}
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
    from_number = params.get("from", "")
    to_number = params.get("to", "")

    form = await request.form()
    _require_twilio_signature(request, form)
    call_sid = params.get("callSid", "") or str(form.get("CallSid") or "").strip()
    call_status = str(form.get("CallStatus") or "").strip()
    call_duration = str(form.get("CallDuration") or "").strip()
    if not from_number:
        from_number = str(form.get("From") or "").strip()
    if not to_number:
        to_number = str(form.get("To") or "").strip()
    direction = params.get("direction", "inbound")

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
                    "direction": direction,
                    "status": call_status,
                    "ended_at": now,
                    "duration_seconds": duration_seconds,
                },
            }
        )

    return PlainTextResponse("OK")


def _relay_text_chunks(value: str) -> list[str]:
    text = normalize_spoken_text(value)
    if not text:
        return ["Sizi dinliyorum. Biraz daha ayrıntı paylaşır mısınız?"]
    chunks = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return chunks or [text]


@app.websocket("/ws/twilio/conversation")
async def twilio_conversation_relay_ws(ws: WebSocket) -> None:
    """Handle Turkish ConversationRelay prompts through the tenant-aware AI endpoint."""
    twilio_verified = verify_twilio_webhook_signature(
        _twilio_public_websocket_url(ws),
        [],
        ws.headers.get("x-twilio-signature", ""),
        settings.TWILIO_AUTH_TOKEN,
    )
    query = ws.query_params
    session = _relay_session_payload(
        tenant_id=query.get("tenant_id", ""),
        call_sid=query.get("call_sid", ""),
        from_number=query.get("from", ""),
        to_number=query.get("to", ""),
        direction=query.get("direction", ""),
    )
    try:
        timestamp = int(query.get("ts", "0"))
    except ValueError:
        timestamp = 0
    verified = verify_websocket_session(
        session,
        query.get("sig", ""),
        timestamp,
        settings.VOICE_GATEWAY_TO_SVONTAI_SECRET,
        settings.TWILIO_RELAY_WS_TOKEN_TTL_SECONDS,
    )
    if (
        not twilio_verified
        or not verified
        or not all(session.values())
        or session["direction"] not in {"inbound", "outbound"}
    ):
        await ws.close(code=1008, reason="Invalid or expired voice session")
        return

    await ws.accept()
    setup_verified = False
    turn = 0
    try:
        while True:
            message = await ws.receive_json()
            message_type = str(message.get("type") or "")
            if message_type == "setup":
                setup_call_sid = str(message.get("callSid") or "").strip()
                if setup_call_sid and setup_call_sid != session["call_sid"]:
                    await ws.close(code=1008, reason="Call identity mismatch")
                    return
                setup_verified = True
                continue
            if message_type in {"interrupt", "agentSpeaking", "clientSpeaking", "tokensPlayed"}:
                continue
            if message_type == "error":
                logger.warning(
                    "ConversationRelay error call_sid=%s description=%s",
                    session["call_sid"],
                    str(message.get("description") or "")[:500],
                )
                continue
            if message_type != "prompt" or message.get("last") is not True:
                continue
            if not setup_verified:
                await ws.close(code=1008, reason="Missing ConversationRelay setup")
                return

            speech = str(message.get("voicePrompt") or "").strip()
            if not speech:
                continue
            turn += 1
            if turn > 30:
                await ws.send_json({
                    "type": "text",
                    "token": "Görüşme süremizin sonuna geldik. Dilerseniz daha sonra yeniden arayabilirsiniz.",
                    "last": True,
                    "interruptible": True,
                    "preemptible": True,
                    "lang": "tr-TR",
                })
                await asyncio.sleep(4)
                await ws.send_json({"type": "end", "handoffData": json.dumps({"reason": "turn_limit"})})
                break

            intent_payload = {
                "tenantId": session["tenant_id"],
                "eventType": "voice_call_intent",
                "eventId": f"twilio:{session['call_sid']}:relay:{turn}",
                "call": {
                    "provider": "twilio",
                    "provider_call_id": session["call_sid"],
                    "direction": session["direction"],
                    "status": "in_progress",
                },
                "from": f"tel:{session['from']}",
                "to": f"tel:{session['to']}",
                "text": speech,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {"turn": turn, "transport": "conversation_relay"},
            }
            try:
                result = await _svontai_post_voice_intent(intent_payload)
            except Exception as exc:
                logger.warning("ConversationRelay backend error: %s", exc, exc_info=True)
                result = {
                    "responseText": "Şu anda bağlantıda kısa bir sorun var. Lütfen biraz sonra yeniden arayın.",
                    "endCall": True,
                }

            response_text = str(
                result.get("responseText")
                or result.get("response_text")
                or "Sizi dinliyorum. Biraz daha ayrıntı paylaşır mısınız?"
            )
            chunks = _relay_text_chunks(response_text)
            for index, chunk in enumerate(chunks):
                await ws.send_json({
                    "type": "text",
                    "token": chunk if index == 0 else f" {chunk}",
                    "last": index == len(chunks) - 1,
                    "interruptible": True,
                    "preemptible": True,
                    "lang": "tr-TR",
                })

            if bool(result.get("endCall") or result.get("end_call")):
                estimated_play_seconds = min(8.0, max(1.5, len(normalize_spoken_text(response_text)) / 14))
                await asyncio.sleep(estimated_play_seconds)
                await ws.send_json({
                    "type": "end",
                    "handoffData": json.dumps({"reason": "conversation_completed"}),
                })
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ConversationRelay WS error: %s", exc, exc_info=True)
        try:
            await ws.close(code=1011, reason="Voice session failed")
        except Exception:
            pass


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
