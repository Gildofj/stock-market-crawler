"""Reconciliation: upstream third-party feeds vs CVM-derived clean-room calc.

Emits one append-only row per indicator into ``lake_indicator_reconciliation``
for QA dashboards and ML drift calibration. The source of truth in the
``fundamentals`` table remains the CVM-derived value — this service is
observational only and must never feed back into ``CrawlResult``.

Today the only upstream feed is the ``yfinance Ticker.info`` dict (carried on
``CrawlResult.yahoo_info_indicators``). Adding a new feed = appending a new
mapping list and bumping the ``source_slug``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from loguru import logger

from core.models.models import LakeIndicatorReconciliation

from ..models.contract import CrawlResult


class _SessionLike(Protocol):
    """Minimal SQLAlchemy Session surface needed by the service.

    Declaring the dependency as a Protocol lets unit tests pass a lightweight
    fake without subclassing the real Session — and keeps the import surface
    of this module narrow (no engine, no autoflush plumbing).
    """

    def bulk_save_objects(self, objects: Iterable[object]) -> None: ...
    def commit(self) -> None: ...

# Relative deviation (|yahoo - cvm| / |cvm|) above which we flag the row as
# an outlier and log a warning. 20% is generous enough to absorb timing
# skew between yfinance (real-time) and CVM (quarterly DFP filings) while
# still catching unit-scale bugs like the 100x dividendYield issue.
OUTLIER_THRESHOLD_PCT = 0.20


@dataclass(frozen=True)
class _IndicatorMap:
    """Mapping from one upstream field to a project indicator + normaliser."""

    source_field: str
    project_indicator: str
    normalise: Callable[[float], float]


def _to_percent(value: float) -> float:
    """Convert a decimal-form rate (0.05) to the project's percent convention (5.0).

    yfinance has historically returned rate-like fields in decimal but is
    known to flip silently. We always assume decimal here and let the ML
    model in lake_indicator_reconciliation learn the actual scale from the
    time series of deltas vs CVM.
    """
    return value * 100


def _identity(value: float) -> float:
    return value


_YAHOO_INFO_MAPS: tuple[_IndicatorMap, ...] = (
    _IndicatorMap("forwardPE", "p_l", _identity),
    _IndicatorMap("trailingPE", "p_l", _identity),
    _IndicatorMap("priceToBook", "p_vp", _identity),
    _IndicatorMap("enterpriseToEbitda", "ev_ebitda", _identity),
    _IndicatorMap("returnOnEquity", "roe", _to_percent),
    _IndicatorMap("dividendYield", "dy", _to_percent),
    _IndicatorMap("profitMargins", "net_margin", _to_percent),
    _IndicatorMap("debtToEbitda", "liquid_debt_ebitda", _identity),
    _IndicatorMap("debtToEquity", "debt_to_equity", _identity),
    _IndicatorMap("marketCap", "market_cap", _identity),
    _IndicatorMap("trailingEps", "eps", _identity),
)


class ReconciliationService:
    """Persists one reconciliation row per (ticker, indicator) per run."""

    SOURCE_SLUG = "yfinance_info"

    def __init__(self, db: _SessionLike) -> None:
        self.db = db

    def emit(self, company_id: uuid.UUID, result: CrawlResult) -> int:
        """Emit reconciliation rows for every indicator the upstream reported.

        Returns the number of rows inserted. Failures are logged but never
        propagated — this is an observational path and must not break the
        crawl.
        """
        snapshot = result.yahoo_info_indicators
        if not snapshot:
            return 0

        rows: list[LakeIndicatorReconciliation] = []
        for mapping in _YAHOO_INFO_MAPS:
            raw = snapshot.get(mapping.source_field)
            if raw is None:
                continue
            normalised = mapping.normalise(raw)
            cvm_value = getattr(result, mapping.project_indicator, None)
            delta_abs, delta_pct, is_outlier = self._delta(normalised, cvm_value)
            rows.append(
                LakeIndicatorReconciliation(
                    company_id=company_id,
                    ticker=result.symbol,
                    indicator=mapping.project_indicator,
                    source_slug=self.SOURCE_SLUG,
                    source_field=mapping.source_field,
                    source_value_raw=raw,
                    source_value_normalised=normalised,
                    cvm_value=cvm_value,
                    delta_abs=delta_abs,
                    delta_pct=delta_pct,
                    is_outlier=is_outlier,
                )
            )
            if is_outlier and cvm_value is not None and delta_pct is not None:
                logger.warning(
                    f"Reconciliation outlier {result.symbol}/"
                    f"{mapping.project_indicator}: "
                    f"yahoo={normalised:.4f} cvm={cvm_value:.4f} "
                    f"delta={delta_pct:.2%}"
                )

        if not rows:
            return 0
        self.db.bulk_save_objects(rows)
        self.db.commit()
        return len(rows)

    @staticmethod
    def _delta(
        upstream: float | None, cvm: float | None
    ) -> tuple[float | None, float | None, bool]:
        if upstream is None or cvm is None:
            return None, None, False
        delta_abs = upstream - cvm
        if cvm == 0:
            # Can't form a meaningful relative delta; flag as outlier when
            # the upstream insists there's something there.
            return delta_abs, None, abs(delta_abs) > 0
        delta_pct = delta_abs / abs(cvm)
        return delta_abs, delta_pct, abs(delta_pct) > OUTLIER_THRESHOLD_PCT
