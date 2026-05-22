from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.context import request_id_var

_HEADER = b"x-request-id"
_CF_HEADER = b"cf-ray"


class CorrelationMiddleware:
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

    typed: Callable[[Message], Awaitable[None]] = send_with_header
    return typed
