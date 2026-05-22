from typing import cast

import pytest

from core.repositories import CompanyRepository
from core.services.lake_service import LakeService
from crawler.spiders.news_spider import NewsSpider, _build_issuer_index


def _spider(known: set[str]) -> NewsSpider:
    return NewsSpider(
        company_repo=cast(CompanyRepository, None),
        lake_service=cast(LakeService, None),
        known_tickers=known,
    )


def test_extract_tickers_returns_empty_on_blank_text():
    spider = _spider({"PETR4", "PETR3"})
    index = _build_issuer_index({"PETR4", "PETR3"})
    assert spider.extract_tickers("", index) == []


def test_extract_tickers_ignores_unknown_symbols():
    index = _build_issuer_index({"PETR4"})
    assert NewsSpider.extract_tickers("ABCD1 announced earnings", index) == []


def test_extract_tickers_expands_to_sibling_share_classes():
    index = _build_issuer_index({"PETR3", "PETR4", "VALE3"})
    assert NewsSpider.extract_tickers("Petrobras (PETR4) sobe hoje", index) == ["PETR3", "PETR4"]


def test_extract_tickers_expands_across_multiple_issuers():
    index = _build_issuer_index({"PETR3", "PETR4", "VALE3", "ITUB3", "ITUB4"})
    text = "Carteira semanal: PETR4 e ITUB4 lideram, VALE3 estável"
    assert NewsSpider.extract_tickers(text, index) == ["ITUB3", "ITUB4", "PETR3", "PETR4", "VALE3"]


def test_extract_tickers_keeps_isolated_ticker_when_no_siblings_known():
    index = _build_issuer_index({"AAPL34"})
    assert NewsSpider.extract_tickers("BDR AAPL34 em alta", index) == ["AAPL34"]


def test_extract_tickers_handles_same_ticker_cited_twice():
    index = _build_issuer_index({"PETR3", "PETR4"})
    text = "PETR4 abriu em alta. Mais sobre PETR4 ao longo do dia."
    assert NewsSpider.extract_tickers(text, index) == ["PETR3", "PETR4"]


def test_build_issuer_index_drops_symbols_shorter_than_prefix():
    index = _build_issuer_index({"ABC", "PETR4"})
    assert "ABC" not in {s for siblings in index.values() for s in siblings}
    assert index["PETR"] == {"PETR4"}


@pytest.mark.asyncio
async def test_resolve_issuer_index_uses_repo_when_not_seeded():
    class _FakeRepo:
        async def get_all_symbols(self) -> set[str]:
            return {"PETR3", "PETR4", "VALE3"}

    spider = NewsSpider(
        company_repo=cast(CompanyRepository, _FakeRepo()),
        lake_service=cast(LakeService, None),
    )
    index = await spider._resolve_issuer_index()
    assert index["PETR"] == {"PETR3", "PETR4"}
    assert index["VALE"] == {"VALE3"}


@pytest.mark.asyncio
async def test_resolve_issuer_index_is_cached_after_first_call():
    calls = {"n": 0}

    class _CountingRepo:
        async def get_all_symbols(self) -> set[str]:
            calls["n"] += 1
            return {"PETR4"}

    spider = NewsSpider(
        company_repo=cast(CompanyRepository, _CountingRepo()),
        lake_service=cast(LakeService, None),
    )
    await spider._resolve_issuer_index()
    await spider._resolve_issuer_index()
    assert calls["n"] == 1
