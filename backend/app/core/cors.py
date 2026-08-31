"""Path-scoped browser-origin enforcement for the public API."""

from __future__ import annotations

from collections.abc import Iterable

from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class StrictCORSMiddleware:
    """Separate authenticated UI CORS from credential-free widget CORS."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        trusted_origins: Iterable[str],
        widget_origins: Iterable[str] = (),
        max_age: int = 600,
    ) -> None:
        self.app = app
        self.trusted_origins = frozenset(trusted_origins)
        self.widget_origins = frozenset(widget_origins) - self.trusted_origins
        if "*" in self.trusted_origins or "*" in self.widget_origins:
            raise ValueError("StrictCORSMiddleware does not permit wildcard origins")

        self.trusted_cors = CORSMiddleware(
            app,
            allow_origins=sorted(self.trusted_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=[
                "Accept",
                "Authorization",
                "Content-Type",
                "X-Request-ID",
                "X-Tenant-ID",
                "X-Widget-Session",
            ],
            expose_headers=["Retry-After", "X-Request-ID"],
            max_age=max_age,
        )
        self.widget_cors = CORSMiddleware(
            app,
            allow_origins=sorted(self.widget_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=[
                "Accept",
                "Content-Type",
                "X-Request-ID",
                "X-Widget-Session",
            ],
            expose_headers=["Retry-After", "X-Request-ID"],
            max_age=max_age,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        origin = Headers(scope=scope).get("origin")
        if not origin:
            await self.app(scope, receive, send)
            return
        if origin in self.trusted_origins:
            await self.trusted_cors(scope, receive, send)
            return
        if origin in self.widget_origins and scope.get("path", "").startswith("/public/"):
            await self.widget_cors(scope, receive, send)
            return

        response = PlainTextResponse(
            "Disallowed CORS origin",
            status_code=403,
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "Vary": "Origin",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
            },
        )
        await response(scope, receive, send)
