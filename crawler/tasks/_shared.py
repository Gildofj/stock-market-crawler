from core.config import settings
from crawler.services.request_manager import RequestManager

_proxies = [p for p in (settings.CRAWLER_HTTP_PROXY, settings.CRAWLER_HTTPS_PROXY) if p]
request_manager = RequestManager(proxies=_proxies or None)
