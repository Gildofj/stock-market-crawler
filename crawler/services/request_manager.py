import random
import time

import requests
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RequestManager:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    def __init__(self, proxies: list = None):
        self.proxies = proxies or []
        self.session = self._create_session()

    def _create_session(self):
        session = requests.Session()
        # Aggressive exponential backoff for 429 and server errors
        retry_strategy = Retry(
            total=4,
            backoff_factor=3,  # Waits: 3s, 6s, 12s, 24s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def get(self, url, **kwargs):
        headers = kwargs.get("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = random.choice(self.USER_AGENTS)

        default_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "DNT": "1",
            "Cache-Control": "max-age=0",
        }

        for key, value in default_headers.items():
            if key not in headers:
                headers[key] = value

        kwargs["headers"] = headers

        if self.proxies:
            proxy = random.choice(self.proxies)
            kwargs["proxies"] = {"http": proxy, "https": proxy}

        # Respectful delay before network call
        time.sleep(random.uniform(1.0, 3.0))

        return self.session.get(url, **kwargs)

