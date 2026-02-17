from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InboundCallRequest:
    provider: str
    to_number: str
    from_number: str
    provider_call_id: str
    raw: dict


class TelephonyAdapter(ABC):
    @abstractmethod
    async def build_connect_stream_response(
        self,
        *,
        tenant_id: str,
        request: InboundCallRequest,
        ws_url: str,
    ) -> str:
        """
        Returns provider-specific response body (e.g., TwiML XML) to connect call audio stream.
        """
        raise NotImplementedError

