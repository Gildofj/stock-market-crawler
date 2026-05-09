import re
import requests
from bs4 import BeautifulSoup
from loguru import logger
from ..services.data_service import DataService

class LogoService:
    """
    Serviço centralizado para buscar logos de empresas de múltiplas fontes.
    """
    def __init__(self, data_service: DataService):
        self.data_service = data_service
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def update_logo_if_missing(self, symbol: str):
        """
        Tenta buscar a logo de várias fontes se ela ainda não existir no banco.
        """
        company = self.data_service.get_company_by_symbol(symbol)
        if company and company.logo_url:
            return company.logo_url

        # Ordem de preferência para fontes de imagem
        sources = [
            self._fetch_from_statusinvest,
            self._fetch_from_fundamentus,
            self._fetch_from_google_finance,
            self._fetch_from_yahoo_finance
        ]

        for source_fn in sources:
            try:
                logo_url = source_fn(symbol)
                if logo_url:
                    self.data_service.update_company_info(symbol, {"logo_url": logo_url})
                    logger.info(f"Logo for {symbol} found via {source_fn.__name__}")
                    return logo_url
            except Exception as e:
                logger.debug(f"Source {source_fn.__name__} failed for {symbol}: {e}")

        return None

    def _fetch_from_statusinvest(self, symbol: str) -> str | None:
        url = f"https://statusinvest.com.br/acoes/{symbol.lower()}"
        response = self.session.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            avatar_div = soup.find('div', class_='avatar')
            if avatar_div and 'style' in avatar_div.attrs:
                match = re.search(r'url\((.*?)\)', avatar_div['style'])
                if match:
                    logo_path = match.group(1).replace("'", "").replace('"', "")
                    return f"https://statusinvest.com.br{logo_path}" if logo_path.startswith('/') else logo_path
        return None

    def _fetch_from_fundamentus(self, symbol: str) -> str | None:
        # Fundamentus às vezes tem a logo ou redireciona para algo com logo
        # Verificando se há alguma imagem de logo no detalhes.php
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={symbol.upper()}"
        response = self.session.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            # Busca por imagens que possam ser a logo (comumente em tabelas de topo)
            img = soup.find('img', alt=re.compile(r'logo', re.I))
            if img and 'src' in img.attrs:
                src = img['src']
                return f"https://www.fundamentus.com.br/{src}" if src.startswith('/') else src
        return None

    def _fetch_from_google_finance(self, symbol: str) -> str | None:
        # Google Finance usa um padrão de favicon via gstatic
        # Mas precisamos do domínio. Uma alternativa rápida é usar o buscador de favicons do Google
        # se tivermos o domínio, ou tentar inferir.
        # Por enquanto, vamos tentar o StatusInvest primeiro que é mais certeiro para B3.
        return None

    def _fetch_from_yahoo_finance(self, symbol: str) -> str | None:
        # Padrão de ticker do Yahoo para Brasil: TICKER.SA
        # Yahoo armazena logos em s.yimg.com mas não é um padrão fixo por ticker.
        return None
