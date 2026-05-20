"""Unit tests for the reconciliation service.

The service compares the raw yfinance ``info`` snapshot (carried on
``CrawlResult.yahoo_info_indicators``) against the CVM-derived value that
just landed on the same ``CrawlResult``. It normalises rate-like fields
from decimal to percent before comparing, computes the delta, flags
outliers, and emits one append-only row per (ticker, indicator).
"""

import uuid
from collections.abc import Iterable

import pytest

from crawler.models.contract import CrawlResult
from crawler.models.models import LakeIndicatorReconciliation
from crawler.services.reconciliation_service import (
    OUTLIER_THRESHOLD_PCT,
    ReconciliationService,
)


class _FakeSession:
    """Minimal stand-in for an SQLAlchemy Session — collects what would be
    persisted so tests can introspect without a real database. Parameter
    names mirror SQLAlchemy's so structural typing (Protocol) succeeds.
    """

    def __init__(self) -> None:
        self.saved: list[LakeIndicatorReconciliation] = []
        self.committed = False

    def bulk_save_objects(self, objects: Iterable[object]) -> None:
        # The service only ever passes reconciliation rows; narrow at the
        # test boundary so assertions can introspect typed attributes.
        for obj in objects:
            assert isinstance(obj, LakeIndicatorReconciliation)
            self.saved.append(obj)

    def commit(self) -> None:
        self.committed = True


def _result(**indicators) -> CrawlResult:
    snapshot = indicators.pop("snapshot", None)
    base = CrawlResult(symbol="TEST3")
    for attr, value in indicators.items():
        setattr(base, attr, value)
    base.yahoo_info_indicators = snapshot
    return base


def test_emit_returns_zero_when_no_snapshot():
    session = _FakeSession()
    result = _result(p_l=10.0)  # CVM has data, but yahoo did not report

    written = ReconciliationService(session).emit(uuid.uuid4(), result)

    assert written == 0
    assert session.saved == []
    assert session.committed is False


def test_emit_records_consistent_dy_decimal_form():
    """Yahoo returns dividendYield in decimal form (0.05). After normalising
    to percent (5.0) it matches the CVM-derived 5.0 — no outlier.
    """
    session = _FakeSession()
    company_id = uuid.uuid4()
    result = _result(dy=5.0, snapshot={"dividendYield": 0.05})

    written = ReconciliationService(session).emit(company_id, result)

    assert written == 1
    row = session.saved[0]
    assert row.indicator == "dy"
    assert row.source_field == "dividendYield"
    assert row.source_value_raw == pytest.approx(0.05)
    assert row.source_value_normalised == pytest.approx(5.0)
    assert row.cvm_value == pytest.approx(5.0)
    assert row.delta_abs == pytest.approx(0.0)
    assert row.delta_pct == pytest.approx(0.0)
    assert row.is_outlier is False


def test_emit_flags_dy_outlier_when_yahoo_returns_percent():
    """If yfinance silently flips to returning percent (5.0) instead of
    decimal (0.05), the normaliser multiplies it again and produces 500%.
    Reconciliation must flag this — exactly the user-reported symptom.
    """
    session = _FakeSession()
    result = _result(dy=5.0, snapshot={"dividendYield": 5.0})

    ReconciliationService(session).emit(uuid.uuid4(), result)

    row = next(r for r in session.saved if r.indicator == "dy")
    assert row.source_value_normalised == pytest.approx(500.0)
    assert row.is_outlier is True
    # delta = (500 - 5) / 5 = 99
    assert row.delta_pct == pytest.approx(99.0)


def test_emit_ratio_fields_pass_through_unscaled():
    """Ratio indicators (P/VP, P/L, EV/EBITDA, ...) use identity normaliser."""
    session = _FakeSession()
    result = _result(
        p_vp=2.0,
        snapshot={"priceToBook": 2.0},
    )

    ReconciliationService(session).emit(uuid.uuid4(), result)

    row = next(r for r in session.saved if r.indicator == "p_vp")
    assert row.source_value_raw == pytest.approx(2.0)
    assert row.source_value_normalised == pytest.approx(2.0)
    assert row.is_outlier is False


def test_emit_handles_missing_cvm_value():
    """When the CVM-derived value is unavailable (e.g. CVM mapping missing),
    we still record the row but with null deltas and is_outlier=False so it
    doesn't pollute outlier dashboards.
    """
    session = _FakeSession()
    # No cvm_value: don't set p_l on the result
    result = _result(snapshot={"forwardPE": 18.0})

    ReconciliationService(session).emit(uuid.uuid4(), result)

    row = next(r for r in session.saved if r.indicator == "p_l")
    assert row.cvm_value is None
    assert row.delta_abs is None
    assert row.delta_pct is None
    assert row.is_outlier is False


def test_emit_handles_zero_cvm_value():
    """A CVM value of exactly zero cannot form a meaningful relative delta,
    but a non-zero yahoo value is still suspicious — flag it.
    """
    session = _FakeSession()
    # dy=0.0 means "no dividends paid" by project convention.
    result = _result(dy=0.0, snapshot={"dividendYield": 0.04})

    ReconciliationService(session).emit(uuid.uuid4(), result)

    row = next(r for r in session.saved if r.indicator == "dy")
    assert row.delta_abs == pytest.approx(4.0)
    assert row.delta_pct is None  # division by zero avoided
    assert row.is_outlier is True


def test_emit_within_threshold_not_flagged():
    """A delta below the configured threshold is recorded but not flagged."""
    session = _FakeSession()
    # delta = (10.5 - 10) / 10 = 0.05 = 5% < threshold (20%)
    result = _result(p_l=10.0, snapshot={"forwardPE": 10.5})

    ReconciliationService(session).emit(uuid.uuid4(), result)

    row = next(r for r in session.saved if r.indicator == "p_l")
    assert row.is_outlier is False
    assert row.delta_pct is not None
    assert abs(row.delta_pct) < OUTLIER_THRESHOLD_PCT


def test_emit_multiple_rows_in_one_run():
    """One row per upstream field present — multiple p_l rows happen
    because forwardPE and trailingPE both map to p_l."""
    session = _FakeSession()
    result = _result(
        p_l=10.0,
        p_vp=2.0,
        dy=5.0,
        snapshot={
            "forwardPE": 10.0,
            "trailingPE": 11.0,
            "priceToBook": 2.0,
            "dividendYield": 0.05,
            "marketCap": 1_000_000_000.0,
        },
    )

    written = ReconciliationService(session).emit(uuid.uuid4(), result)

    indicators_seen = [row.indicator for row in session.saved]
    # 2 rows for p_l (forwardPE, trailingPE), 1 each for p_vp, dy, market_cap
    assert written == 5
    assert indicators_seen.count("p_l") == 2
    assert "p_vp" in indicators_seen
    assert "dy" in indicators_seen
    assert "market_cap" in indicators_seen


def test_emit_carries_ticker_and_source_slug():
    session = _FakeSession()
    result = _result(p_l=10.0, snapshot={"forwardPE": 10.0})
    company_id = uuid.uuid4()

    ReconciliationService(session).emit(company_id, result)

    row = session.saved[0]
    assert row.ticker == "TEST3"
    assert row.source_slug == "yfinance_info"
    assert row.company_id == company_id
