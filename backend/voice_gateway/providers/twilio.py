from .base import InboundCallRequest, TelephonyAdapter
from voice_gateway.twiml import say


class TwilioAdapter(TelephonyAdapter):
    async def build_connect_stream_response(
        self,
        *,
        tenant_id: str,
        request: InboundCallRequest,
        ws_url: str,
    ) -> str:
        # Avoid adding twilio sdk dependency; return raw TwiML.
        # Twilio will open a WebSocket to ws_url (wss recommended in production).
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  {say("Merhaba. SvontAI arama asistanına hoş geldiniz.")}
  <Connect>
    <Stream url="{ws_url}">
      <Parameter name="tenant_id" value="{tenant_id}" />
      <Parameter name="call_sid" value="{request.provider_call_id}" />
      <Parameter name="from" value="{request.from_number}" />
      <Parameter name="to" value="{request.to_number}" />
    </Stream>
  </Connect>
</Response>"""
