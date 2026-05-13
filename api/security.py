import ipaddress
import os
import secrets
import time

import httpx
from fastapi import HTTPException, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(provided: str | None = Security(_api_key_header)) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured on server.",
        )
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


class CloudflareMiddleware(BaseHTTPMiddleware):
    """
    Middleware que garante que as requisições venham apenas de IPs oficiais da Cloudflare.
    """

    def __init__(self, app):
        super().__init__(app)
        self.cloudflare_ips = []
        self.last_update = 0
        self._update_interval = 86400  # 24 horas

    async def _get_cloudflare_ips(self):
        if time.time() - self.last_update < self._update_interval and self.cloudflare_ips:
            return self.cloudflare_ips

        try:
            async with httpx.AsyncClient() as client:
                v4 = await client.get("https://www.cloudflare.com/ips-v4")
                v6 = await client.get("https://www.cloudflare.com/ips-v6")

                ips = []
                for line in v4.text.splitlines():
                    if line.strip():
                        ips.append(ipaddress.ip_network(line.strip()))
                for line in v6.text.splitlines():
                    if line.strip():
                        ips.append(ipaddress.ip_network(line.strip()))

                self.cloudflare_ips = ips
                self.last_update = time.time()
                logger.info(f"Cloudflare IPs updated: {len(self.cloudflare_ips)} ranges found.")
        except Exception as e:
            logger.error(f"Failed to update Cloudflare IPs: {e}")
            # Se falhar, mantém os antigos se existirem

        return self.cloudflare_ips

    async def dispatch(self, request: Request, call_next):
        # Allow documentation and health routes to bypass Cloudflare check
        bypass_paths = ["/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"]
        if request.url.path in bypass_paths:
            return await call_next(request)

        client_ip = request.client.host

        # Check if Strict mode is enabled
        is_strict = os.getenv("CLOUDFLARE_STRICT", "true").lower() == "true"

        # Simplificação: Validar se o cabeçalho 'cf-connecting-ip' está presente.
        # Se não estiver, a requisição não passou pela Cloudflare.
        if not request.headers.get("cf-connecting-ip"):
            if is_strict:
                logger.warning(
                    f"Blocked request from {client_ip}: Missing 'cf-connecting-ip' header."
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Direct access forbidden. Use the official domain."},
                )
            else:
                logger.debug(
                    f"Allowing request from {client_ip} without CF headers (STRICT=false)."
                )

        response = await call_next(request)
        return response
