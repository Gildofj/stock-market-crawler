import random
import time

import requests
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RequestManager:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",  # noqa: E501
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",  # noqa: E501
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",  # noqa: E501
    ]

    def __init__(self, proxies: list = None):
        self.proxies = proxies or []
        self.session = self._cria_session()

    def _cria_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def get(self, url, **kwargs):
        headers = kwargs.get("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = random.choice(self.USER_AGENTS)

        kwargs["headers"] = headers

        if self.proxies:
            proxy = random.choice(self.proxies)
            kwargs["proxies"] = {"http": proxy, "https": proxy}
            logger.debug(f"Using proxy: {proxy}")

        # Intelligent delay to avoid overwhelming servers
        time.sleep(random.uniform(0.5, 1.5))

        return self.session.get(url, **kwargs)

