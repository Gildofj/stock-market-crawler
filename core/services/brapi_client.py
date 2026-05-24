"""Brapi REST client (https://brapi.dev).

Centralises every outbound call to Brapi so spiders and the universe-refresh
job share quota tracking and response parsing. The free tier allows 15k
requests/month — the in-memory monthly counter logs a warning when usage
crosses 80% so the operator can react before tasks start failing.

The client is intentionally synchronous; spiders run inside asyncio.to_thread
when they call it. No retries: Brapi 429s are reported up and the calling
spider decides whether to backoff or skip.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from loguru import logger

from core.config import settings

_BASE_URL = "https://brapi.dev/api"
_WARN_QUOTA_RATIO = 0.8


class BrapiQuotaExceededError(RuntimeError):
    """Raised when the configured monthly budget would be exceeded."""


class BrapiUnauthorizedError(RuntimeError):
    """Raised on 401 — missing or invalid BRAPI_TOKEN."""


@dataclass(frozen=True)
class BrapiQuote:
    ticker: str
    cnpj: str | None
    long_name: str | None
    sector: str | None
    industry: str | None
    asset_type: str | None  # quoteType normalised: EQUITY | FII | BDR | ETF | UNIT
    market_cap: float | None
    raw: dict[str, Any]


class BrapiClient:
    """Singleton-ish Brapi wrapper. Tracks monthly call count process-wide.

    Note: counter resets on process restart. Acceptable for a job that runs
    once a week — for hot paths consider persisting the counter in Redis or
    Postgres if budget governance becomes critical.
    """

    def __init__(
        self,
        token: str | None = None,
        monthly_budget: int = 15_000,
        timeout: float = 15.0,
    ) -> None:
        self._token = token if token is not None else settings.BRAPI_TOKEN
        self._budget = monthly_budget
        self._timeout = timeout
        self._lock = threading.Lock()
        self._month_key = self._current_month_key()
        self._calls_this_month = 0

    @staticmethod
    def _current_month_key() -> str:
        now = datetime.now(UTC)
        return f"{now.year:04d}-{now.month:02d}"

    def _check_quota(self) -> None:
        with self._lock:
            current = self._current_month_key()
            if current != self._month_key:
                self._month_key = current
                self._calls_this_month = 0
            if self._calls_this_month >= self._budget:
                raise BrapiQuotaExceededError(
                    f"Brapi monthly budget exhausted: {self._calls_this_month}/{self._budget}"
                )
            self._calls_this_month += 1
            if (
                self._calls_this_month == int(self._budget * _WARN_QUOTA_RATIO)
                or self._calls_this_month == self._budget - 1
            ):
                logger.warning(
                    f"BrapiClient: {self._calls_this_month}/{self._budget} calls used "
                    f"this month ({self._month_key})"
                )

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    @property
    def calls_used(self) -> int:
        return self._calls_this_month

    def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._token:
            raise BrapiUnauthorizedError("BRAPI_TOKEN not configured")
        self._check_quota()
        url = f"{_BASE_URL}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=self._timeout)
        except httpx.HTTPError as exc:
            logger.warning(f"BrapiClient: network error on {path}: {exc}")
            raise
        if response.status_code == 401:
            raise BrapiUnauthorizedError(f"Brapi rejected token on {path}")
        response.raise_for_status()
        return response.json()

    def list_available_tickers(self) -> list[str]:
        """Returns every ticker tradeable on B3 known to Brapi (~700 entries)."""
        payload = self._request("/available")
        stocks = payload.get("stocks") or []
        return sorted({str(t).upper() for t in stocks if t})

    def fetch_quote(
        self, ticker: str, modules: tuple[str, ...] = ("summaryProfile",)
    ) -> BrapiQuote | None:
        params = {"modules": ",".join(modules)} if modules else None
        try:
            payload = self._request(f"/quote/{ticker}", params=params)
        except BrapiUnauthorizedError:
            raise
        except Exception as exc:
            logger.warning(f"BrapiClient: quote fetch failed for {ticker}: {exc}")
            return None

        results = (payload or {}).get("results") or []
        if not results:
            return None
        row = results[0]

        profile = row.get("summaryProfile") or {}
        cnpj_raw = row.get("cnpj") or profile.get("cnpj")
        cnpj_digits = "".join(ch for ch in str(cnpj_raw) if ch.isdigit()) if cnpj_raw else None

        asset_type = _normalise_asset_type(
            quote_type=row.get("quoteType"),
            symbol=ticker,
        )

        return BrapiQuote(
            ticker=ticker.upper(),
            cnpj=cnpj_digits or None,
            long_name=row.get("longName") or row.get("shortName"),
            sector=profile.get("sector") or row.get("sector"),
            industry=profile.get("industry") or row.get("industry"),
            asset_type=asset_type,
            market_cap=_coerce_float(row.get("marketCap")),
            raw=row,
        )


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_asset_type(quote_type: str | None, symbol: str) -> str:
    """Hybrid classification: Brapi's quoteType disambiguates suffix 11 between
    FII / ETF / UNIT (e.g. BOVA11 is an ETF, MXRF11 is a FII), but the suffix
    is authoritative for BDRs and most equities since Brapi often tags BDRs as
    plain EQUITY.

    Order:
        1. quote_type=ETF → ETF (suffix 11 is ambiguous; trust Brapi here)
        2. B3 suffix rules — 11→FII, 32/33/34/35→BDR
        3. quote_type=MUTUALFUND → FII (fallback for non-11 funds)
        4. Default EQUITY (ON/PN/PNA/PNB tickers ending 3/4/5/6)

    Fractional suffix "F" is stripped before evaluation.
    """
    qt = (quote_type or "").upper()
    if qt == "ETF":
        return "ETF"

    cleaned = symbol.upper().replace(".SA", "").rstrip("F")
    if cleaned.endswith("11"):
        return "FII"
    if cleaned.endswith(("32", "33", "34", "35")):
        return "BDR"
    if qt == "MUTUALFUND":
        return "FII"
    return "EQUITY"


_default_client: BrapiClient | None = None


def get_brapi_client() -> BrapiClient:
    global _default_client
    if _default_client is None:
        _default_client = BrapiClient()
    return _default_client
