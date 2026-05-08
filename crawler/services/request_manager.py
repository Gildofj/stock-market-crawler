import random
import requests
from loguru import logger

class RequestManager:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    ]

    def __init__(self, proxies: list = None):
        self.proxies = proxies or []

    def get(self, url, **kwargs):
        headers = kwargs.get("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = random.choice(self.USER_AGENTS)
        
        kwargs["headers"] = headers
        
        if self.proxies:
            proxy = random.choice(self.proxies)
            kwargs["proxies"] = {"http": proxy, "https": proxy}
            logger.debug(f"Using proxy: {proxy}")

        return requests.get(url, **kwargs)
