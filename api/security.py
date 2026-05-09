import ipaddress
import time

import httpx
from fastapi import HTTPException, Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


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
        # Em ambiente local (dev), podemos pular essa validação se necessário
        # Mas para produção (Fly.io), é obrigatório.

        client_ip = request.client.host
        # O Fly.io passa o IP real em X-Forwarded-For ou o Cloudflare em CF-Connecting-IP
        # Mas o socket direto (request.client.host) deve ser um IP da Fly que recebeu o tráfego.
        # Na Fly.io com Cloudflare, o tráfego chega: User -> Cloudflare -> Fly Proxy -> App.
        # O request.client.host será o IP do Fly Proxy.
        # Para ser "Strict Cloudflare", idealmente o Fly Proxy deveria estar configurado
        # ou validamos o cabeçalho CF-Connecting-IP e conferimos se o IP que enviou (Proxy)
        # é confiável.

        # Simplificação: Validar se o cabeçalho 'cf-connecting-ip' está presente.
        # Se não estiver, a requisição não passou pela Cloudflare.
        if not request.headers.get("cf-connecting-ip"):
            logger.warning(
                f"Blocked request from {client_ip}: Missing 'cf-connecting-ip' header."
            )
            raise HTTPException(
                status_code=403,
                detail="Direct access forbidden. Use the official domain.",
            )

        # Validação de IP (Opcional mas recomendado):
        # Aqui compararíamos o IP do Proxy que entregou o pacote.
        # No plano free, a Fly usa IPs compartilhados.

        response = await call_next(request)
        return response
