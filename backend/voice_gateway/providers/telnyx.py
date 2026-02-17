from .base import InboundCallRequest, TelephonyAdapter


class TelnyxAdapter(TelephonyAdapter):
    async def build_connect_stream_response(
        self,
        *,
        tenant_id: str,
        request: InboundCallRequest,
        ws_url: str,
    ) -> str:
        # Placeholder: Telnyx Call Control / WebSocket media differs from Twilio.
        # We keep adapter interface to avoid lock-in; implement after provider account setup.
        raise NotImplementedError("Telnyx streaming response is not implemented yet.")

