"""Correlation-ID middleware.

Reads ``X-Request-Id`` from the incoming request (or ``Cf-Ray`` when Cloudflare
is in front), generates a UUID4 when neither is present, binds the value to
:data:`core.context.request_id_var` so every log line emitted while serving
the request carries the same ``request_id``, and echoes it back on the
response so callers can quote it when reporting issues.

Implemented as a pure ASGI middleware rather than ``BaseHTTPMiddleware`` to
sidestep the long-standing Starlette issue where ``ContextVar`` tokens set in
the middleware coroutine are not visible to the downstream handler running in
a different anyio task.

Should be registered **last** in ``api/main.py`` so it becomes the outermost
middleware — that way every request, including those rejected by CORS or by
``CloudflareMiddleware``, still gets a correlation id in its logs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.context import request_id_var

_HEADER = b"x-request-id"
_CF_HEADER = b"cf-ray"


class CorrelationMiddleware:
    """Pure ASGI middleware that attaches a per-request correlation id."""

    def __init__(self, app: ASGIApp, header_name: str = "x-request-id") -> None:
        self.app = app
        self._header = header_name.lower().encode("ascii")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = _extract_request_id(scope.get("headers", []), self._header)
        token = request_id_var.set(rid)

        send_with_header = _wrap_send(send, self._header, rid.encode("ascii"))

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            request_id_var.reset(token)


def _extract_request_id(headers: list[tuple[bytes, bytes]], header: bytes) -> str:
    found: bytes | None = None
    cf: bytes | None = None
    for key, value in headers:
        lowered = key.lower()
        if lowered == header:
            found = value
        elif lowered == _CF_HEADER:
            cf = value
    chosen = found or cf
    return chosen.decode("ascii", errors="replace") if chosen else uuid4().hex


def _wrap_send(send: Send, header: bytes, value: bytes) -> Send:
    async def send_with_header(message: Message) -> None:
        if message["type"] == "http.response.start":
            existing = [(k, v) for k, v in message.get("headers", []) if k.lower() != header]
            existing.append((header, value))
            message["headers"] = existing
        await send(message)

    # `Send` is a Callable[[Message], Awaitable[None]] — confirm the alias to
    # keep type-checkers from widening on the closure.
    typed: Callable[[Message], Awaitable[None]] = send_with_header
    return typed
