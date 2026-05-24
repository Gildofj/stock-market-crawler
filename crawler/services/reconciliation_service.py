from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.models import LakeIndicatorReconciliation

from ..models.contract import CrawlResult


class _SessionLike(Protocol):
    async def commit(self) -> None: ...
    def add_all(self, instances: Iterable[object]) -> None: ...


OUTLIER_THRESHOLD_PCT = 0.20


@dataclass(frozen=True)
class _IndicatorMap:
    source_field: str
    project_indicator: str
    normalise: Callable[[float], float]


def _to_percent(value: float) -> float:
    return value * 100


def _identity(value: float) -> float:
    return value


_YAHOO_INFO_MAPS: tuple[_IndicatorMap, ...] = (
    _IndicatorMap("forwardPE", "p_l", _identity),
    _IndicatorMap("trailingPE", "p_l", _identity),
    _IndicatorMap("priceToBook", "p_vp", _identity),
    _IndicatorMap("enterpriseToEbitda", "ev_ebitda", _identity),
    _IndicatorMap("returnOnEquity", "roe", _to_percent),
    # yfinance >=0.2.51 returns dividendYield as a percentage (e.g. 8.72), not a fraction.
    _IndicatorMap("dividendYield", "dy", _identity),
    _IndicatorMap("profitMargins", "net_margin", _to_percent),
    _IndicatorMap("debtToEbitda", "liquid_debt_ebitda", _identity),
    _IndicatorMap("debtToEquity", "debt_to_equity", _identity),
    _IndicatorMap("marketCap", "market_cap", _identity),
    _IndicatorMap("trailingEps", "eps", _identity),
)


class ReconciliationService:
    SOURCE_SLUG = "yfinance_info"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def emit(self, company_id: uuid.UUID, result: CrawlResult) -> int:
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
        self.db.add_all(rows)
        try:
            await self.db.commit()
            return len(rows)
        except Exception as exc:
            # Roll back so the caller's session stays usable for subsequent stages.
            await self.db.rollback()
            logger.warning(f"Reconciliation persistence failed for {result.symbol}: {exc}")
            return 0

    @staticmethod
    def _delta(
        upstream: float | None, cvm: float | None
    ) -> tuple[float | None, float | None, bool]:
        if upstream is None or cvm is None:
            return None, None, False
        delta_abs = upstream - cvm
        if cvm == 0:
            return delta_abs, None, abs(delta_abs) > 0
        delta_pct = delta_abs / abs(cvm)
        return delta_abs, delta_pct, abs(delta_pct) > OUTLIER_THRESHOLD_PCT
