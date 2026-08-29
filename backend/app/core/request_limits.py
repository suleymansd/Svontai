"""ASGI request body size enforcement."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Reject oversized fixed-length and chunked request bodies with HTTP 413."""

    def __init__(
        self,
        app: Any,
        *,
        default_limit: int,
        path_limits: dict[str, int] | None = None,
    ) -> None:
        self.app = app
        self.default_limit = default_limit
        self.path_limits = path_limits or {}

    def _limit_for(self, path: str) -> int:
        matches = [
            (prefix, limit)
            for prefix, limit in self.path_limits.items()
            if path.startswith(prefix)
        ]
        return max(matches, key=lambda item: len(item[0]))[1] if matches else self.default_limit

    async def __call__(self, scope: dict, receive: Callable[[], Awaitable[dict]], send: Callable[[dict], Awaitable[None]]) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        limit = self._limit_for(scope.get("path", ""))
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        try:
            content_length = int(headers.get(b"content-length", b"0") or b"0")
        except ValueError:
            content_length = 0
        if content_length > limit:
            await self._reject(send)
            return

        consumed = 0

        async def limited_receive() -> dict:
            nonlocal consumed
            message = await receive()
            if message.get("type") == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await self._reject(send)

    @staticmethod
    async def _reject(send: Callable[[dict], Awaitable[None]]) -> None:
        body = b'{"detail":"Request body too large"}'
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"connection", b"close"),
            ],
        })
        await send({"type": "http.response.body", "body": body})
