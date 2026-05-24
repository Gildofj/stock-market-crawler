import json
import os
import re
import tempfile
import time
from pathlib import Path

from bs4 import BeautifulSoup
from loguru import logger

from crawler.services.request_manager import RequestManager


def _default_cache_dir() -> Path:
    override = os.getenv("CVM_CACHE_DIR")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "cvm_cache"


class B3BDRCatalogService:
    CACHE_TTL_DAYS = 7
    JSON_URL = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompaniesPagination/eyJsYW5ndWFnZSI6InB0LWJyIiwicGFnZU51bWJlciI6MSwicGFnZVNpemUiOjIwMDAsInR5cGUiOjJ9"
    HTML_URL = "https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/lista-de-bdrs-por-pais-do-emissor/"

    def __init__(
        self,
        request_manager: RequestManager | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.request_manager = request_manager or RequestManager()
        self.cache_dir = cache_dir or _default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[str, float]] | None = None

    def _cached_path(self, name: str) -> Path:
        return self.cache_dir / name

    def _is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age_days = (time.time() - path.stat().st_mtime) / (3600.0 * 24.0)
        return age_days < self.CACHE_TTL_DAYS

    def get_bdr_metadata(self) -> dict[str, tuple[str, float]]:
        if self._cache is not None:
            return self._cache

        cached = self._cached_path("b3_bdr_catalog.json")
        if self._is_fresh(cached):
            try:
                with open(cached, encoding="utf-8") as f:
                    data = json.load(f)
                self._cache = data
                return data
            except Exception as exc:
                logger.error(f"B3BDRCatalogService: failed to read cache: {exc}")

        data = self._fetch_via_json()
        if not data:
            logger.info("B3BDRCatalogService: JSON endpoint empty or failed; trying HTML fallback.")
            data = self._fetch_via_html()

        if data:
            try:
                with open(cached, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            except Exception as exc:
                logger.error(f"B3BDRCatalogService: failed to write cache: {exc}")
            self._cache = data

        return data or {}

    def _fetch_via_json(self) -> dict[str, tuple[str, float]]:
        # The JSON endpoint returns issuer-level metadata; the foreign
        # underlying ticker is not always present, so we fall back to the
        # company-name prefix and ratio=1.0 when fields are missing. The
        # HTML fallback (_fetch_via_html) is the higher-fidelity path
        # whenever the JSON one is blocked or shape-shifts.
        try:
            response = self.request_manager.get(self.JSON_URL, timeout=30)
            response.raise_for_status()
            payload = response.json()

            results: dict[str, tuple[str, float]] = {}
            for item in payload.get("results", []):
                ticker = item.get("issuingCompany")
                underlying = item.get("companyName")
                if ticker:
                    results[ticker] = (underlying or ticker[:4], 1.0)

            return results
        except Exception as exc:
            logger.debug(f"B3BDRCatalogService JSON fetch failed: {exc}")
            return {}

    def _fetch_via_html(self) -> dict[str, tuple[str, float]]:
        try:
            response = self.request_manager.get(self.HTML_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            results = {}
            for row in soup.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 3:
                    ticker = cols[0].text.strip()
                    underlying = cols[1].text.strip()
                    ratio_text = cols[2].text.strip()
                    ratio = 1.0
                    try:
                        # Extract ratio "1 BDR = 2 Ações" etc.
                        match = re.search(r"(\d+)", ratio_text)
                        if match:
                            ratio = float(match.group(1))
                    except Exception:
                        pass
                    if ticker:
                        results[ticker] = (underlying, ratio)
            return results
        except Exception as exc:
            logger.error(f"B3BDRCatalogService HTML fetch failed: {exc}")
            return {}
