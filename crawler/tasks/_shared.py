from loguru import logger

from core.config import settings
from crawler.services.cvm_dataset_service import CVMDatasetService
from crawler.services.request_manager import RequestManager
from crawler.spiders.cvm_spider import CVMSpider


def _validate_proxy(proxy: str | None) -> str | None:
    # curl_cffi takes the proxy URL as-is — it needs inline credentials
    # (`http://user:pass@host:port`). A bare `http://host:port` ends up
    # producing 407 Proxy Authentication Required for every request, which
    # is the exact failure observed when the webshare secret rotates and
    # someone re-deploys before refreshing CRAWLER_HTTP_PROXY.
    if not proxy:
        return None
    if "://" not in proxy:
        logger.warning(
            f"_shared: proxy URL missing scheme ({proxy!r}); ignoring to avoid 407 storm."
        )
        return None
    scheme, _, rest = proxy.partition("://")
    if "@" not in rest:
        logger.warning(
            f"_shared: proxy URL has no credentials ({scheme}://...); ignoring to avoid 407."
        )
        return None
    return proxy


_proxies = [
    validated
    for validated in (
        _validate_proxy(settings.CRAWLER_HTTP_PROXY),
        _validate_proxy(settings.CRAWLER_HTTPS_PROXY),
    )
    if validated
]
request_manager = RequestManager(proxies=_proxies or None)

_dataset_service = CVMDatasetService(request_manager=request_manager)
cvm_spider_singleton = CVMSpider(dataset_service=_dataset_service)
