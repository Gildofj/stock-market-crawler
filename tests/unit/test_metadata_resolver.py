import pytest

from crawler.models.contract import CrawlResult
from crawler.services.metadata_resolver import MetadataResolver


class _FakeDataset:
    def __init__(self, sectors: dict[str, str]) -> None:
        self._sectors = sectors

    def get_sector_by_cvm_code(self) -> dict[str, str]:
        return self._sectors


class _FakeCvmSpider:
    def __init__(self, codes: dict[str, str], sectors: dict[str, str]) -> None:
        self._codes = codes
        self.dataset_service = _FakeDataset(sectors)

    def get_cvm_code(self, ticker: str) -> str | None:
        return self._codes.get(ticker.upper())


class _FakeLogoService:
    def __init__(self, logo: str | None = None) -> None:
        self.logo = logo
        self.calls: list[tuple[str, str | None]] = []

    async def resolve(self, symbol: str, website: str | None) -> str | None:
        self.calls.append((symbol, website))
        return self.logo


@pytest.mark.asyncio
async def test_sector_filled_from_cvm_when_yfinance_missing():
    cvm = _FakeCvmSpider(codes={"PETR4": "9512"}, sectors={"9512": "Petróleo, Gás e Energia"})
    resolver = MetadataResolver(cvm, _FakeLogoService())  # type: ignore[arg-type]
    result = CrawlResult(symbol="PETR4", sector=None)

    await resolver.apply(result)

    assert result.sector == "Petróleo, Gás e Energia"


@pytest.mark.asyncio
async def test_yfinance_sector_is_not_overwritten_by_cvm():
    cvm = _FakeCvmSpider(codes={"PETR4": "9512"}, sectors={"9512": "Petróleo"})
    resolver = MetadataResolver(cvm, _FakeLogoService())  # type: ignore[arg-type]
    result = CrawlResult(symbol="PETR4", sector="Energy")

    await resolver.apply(result)

    assert result.sector == "Energy"


@pytest.mark.asyncio
async def test_override_fills_fii_metadata_when_no_cvm_match():
    cvm = _FakeCvmSpider(codes={}, sectors={})
    resolver = MetadataResolver(cvm, _FakeLogoService())  # type: ignore[arg-type]
    result = CrawlResult(symbol="HGLG11")

    await resolver.apply(result)

    assert result.sector == "Real Estate"
    assert result.sub_sector == "REIT"
    assert result.segment == "Logistics"


@pytest.mark.asyncio
async def test_override_logo_takes_priority_over_logo_service():
    cvm = _FakeCvmSpider(codes={}, sectors={})
    logo = _FakeLogoService(logo="https://logo.clearbit.com/apple.com")
    resolver = MetadataResolver(cvm, logo)  # type: ignore[arg-type]
    result = CrawlResult(symbol="AAPL34", website="https://apple.com")

    await resolver.apply(result)

    assert result.logo_url == "https://logo.clearbit.com/apple.com"


@pytest.mark.asyncio
async def test_logo_service_invoked_when_no_override():
    cvm = _FakeCvmSpider(codes={}, sectors={})
    logo = _FakeLogoService(logo="https://logo.clearbit.com/petrobras.com.br")
    resolver = MetadataResolver(cvm, logo)  # type: ignore[arg-type]
    result = CrawlResult(symbol="PETR4", website="https://petrobras.com.br")

    await resolver.apply(result)

    assert result.logo_url == "https://logo.clearbit.com/petrobras.com.br"
    assert logo.calls == [("PETR4", "https://petrobras.com.br")]


@pytest.mark.asyncio
async def test_logo_service_failure_is_swallowed():
    class _ExplodingLogo:
        async def resolve(self, symbol, website):
            raise RuntimeError("boom")

    cvm = _FakeCvmSpider(codes={}, sectors={})
    resolver = MetadataResolver(cvm, _ExplodingLogo())  # type: ignore[arg-type]
    result = CrawlResult(symbol="PETR4", website="https://petrobras.com.br")

    await resolver.apply(result)

    assert result.logo_url is None


@pytest.mark.asyncio
async def test_sector_map_is_cached_across_calls():
    fetches = {"n": 0}

    class _CountingDataset:
        def get_sector_by_cvm_code(self) -> dict[str, str]:
            fetches["n"] += 1
            return {"9512": "Petróleo"}

    cvm = _FakeCvmSpider(codes={"PETR4": "9512"}, sectors={})
    cvm.dataset_service = _CountingDataset()  # type: ignore[assignment]
    resolver = MetadataResolver(cvm, _FakeLogoService())  # type: ignore[arg-type]

    await resolver.apply(CrawlResult(symbol="PETR4"))
    await resolver.apply(CrawlResult(symbol="PETR4"))

    assert fetches["n"] == 1
