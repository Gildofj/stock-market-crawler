import ipaddress
import os
import secrets
import time

import httpx
from fastapi import HTTPException, Request, Security, status
from fastapi.responses import ORJSONResponse
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
    def __init__(self, app):
        super().__init__(app)
        self.cloudflare_ips = []
        self.last_update = 0
        self._update_interval = 86400

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

        return self.cloudflare_ips

    async def dispatch(self, request: Request, call_next):
        bypass_paths = ["/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"]
        if request.url.path in bypass_paths:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        cf_connecting_ip = request.headers.get("cf-connecting-ip")

        is_strict = os.getenv("CLOUDFLARE_STRICT", "false").lower() == "true"

        if not cf_connecting_ip:
            if is_strict:
                logger.warning(
                    f"Blocked request from {client_ip}: Missing 'cf-connecting-ip' header. "
                    "This request did not pass through Cloudflare Proxy or headers were stripped."
                )
                return ORJSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "Direct access forbidden. Use the official domain via Cloudflare."
                        )
                    },
                )
            else:
                logger.info(
                    f"Allowing non-proxied request from {client_ip} (CLOUDFLARE_STRICT is false)."
                )
        else:
            logger.debug(
                f"Verified Cloudflare request from {cf_connecting_ip} (Proxy: {client_ip})"
            )

        response = await call_next(request)
        return response
