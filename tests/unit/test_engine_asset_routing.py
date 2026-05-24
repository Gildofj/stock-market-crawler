"""Unit tests for CrawlerEngine asset-type-based routing."""

from __future__ import annotations

import pytest

from crawler.engine.crawler_engine import _infer_asset_type, symbol_key


def test_symbol_key_strips_sa_and_uppercases():
    assert symbol_key("petr4.sa") == "PETR4"
    assert symbol_key("MXRF11") == "MXRF11"


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("PETR4", "EQUITY"),
        ("VALE3", "EQUITY"),
        ("PETR4F", "EQUITY"),
        ("MXRF11", "FII"),
        ("HGLG11", "FII"),
        ("MXRF11F", "FII"),
        ("AAPL34", "BDR"),
        ("MSFT34", "BDR"),
        ("GOGL35", "BDR"),
        ("ITLC33", "BDR"),
        ("AMZO32", "BDR"),
    ],
)
def test_infer_asset_type(symbol: str, expected: str):
    assert _infer_asset_type(symbol) == expected
