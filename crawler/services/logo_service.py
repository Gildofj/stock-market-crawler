import re

from bs4 import BeautifulSoup
from loguru import logger

from ..services.data_service import DataService
from ..services.request_manager import RequestManager


class LogoService:
    """
    Serviço para busca manual de logos.
    Nota: Os spiders agora extraem logos durante o crawl principal para eficiência.
    """

    def __init__(self, data_service: DataService):
        self.data_service = data_service
        self.request_manager = RequestManager()

    def update_logo_if_missing(self, symbol: str):
        company = self.data_service.get_company_by_symbol(symbol)
        if company and hasattr(company, "logo_url") and company.logo_url:
            return str(company.logo_url)

        sources = [
            self._fetch_from_statusinvest,
            self._fetch_from_fundamentus
        ]

        for source_fn in sources:
            try:
                logo_url = source_fn(symbol)
                if logo_url:
                    self.data_service.update_company_info(symbol, {"logo_url": logo_url})
                    logger.info(f"Logo for {symbol} found via {source_fn.__name__}")
                    return logo_url
            except Exception as e:
                logger.debug(f"Logo source {source_fn.__name__} failed for {symbol}: {e}")

        return None

    def _fetch_from_statusinvest(self, symbol: str) -> str | None:
        url = f"https://statusinvest.com.br/acoes/{symbol.lower()}"
        response = self.request_manager.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            avatar_div = soup.find('div', class_='avatar')
            if avatar_div and avatar_div.has_attr('style'):
                style_attr = avatar_div.get('style')
                if isinstance(style_attr, list):
                    style_attr = " ".join(style_attr)

                match = re.search(r'url\((.*?)\)', str(style_attr))
                if match:
                    logo_path = match.group(1).replace("'", "").replace('"', "")
                    return f"https://statusinvest.com.br{logo_path}" if logo_path.startswith("/") else logo_path
        return None

    def _fetch_from_fundamentus(self, symbol: str) -> str | None:
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={symbol.upper()}"
        response = self.request_manager.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            img = soup.find('img', alt=re.compile(r'logo', re.I))
            if img and img.has_attr('src'):
                src = img.get('src')
                if isinstance(src, list):
                    src = src[0]

                src_str = str(src)
                return f"https://www.fundamentus.com.br/{src_str}" if src_str.startswith('/') else src_str
        return None
        return None
