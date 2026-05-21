import pytest

from crawler.services.logo_service import LogoService, _clearbit_url


def test_clearbit_url_from_full_url():
    assert _clearbit_url("https://petrobras.com.br") == "https://logo.clearbit.com/petrobras.com.br"


def test_clearbit_url_strips_www():
    assert _clearbit_url("https://www.itau.com.br/") == "https://logo.clearbit.com/itau.com.br"


def test_clearbit_url_from_bare_domain():
    assert _clearbit_url("vale.com") == "https://logo.clearbit.com/vale.com"


def test_clearbit_url_returns_none_for_invalid():
    assert _clearbit_url("") is None


@pytest.mark.asyncio
async def test_resolve_prefers_override(company_repo):
    service = LogoService(company_repo)
    logo = await service.resolve("AAPL34", "https://apple.com")
    assert logo == "https://logo.clearbit.com/apple.com"


@pytest.mark.asyncio
async def test_resolve_falls_back_to_clearbit_when_scrape_yields_nothing(company_repo, monkeypatch):
    service = LogoService(company_repo)

    async def _no_scrape(self, site_url):
        return None

    monkeypatch.setattr(LogoService, "_extract_logo_from_site", _no_scrape)
    logo = await service.resolve("PETR4", "https://petrobras.com.br")
    assert logo == "https://logo.clearbit.com/petrobras.com.br"


@pytest.mark.asyncio
async def test_resolve_returns_none_without_website_or_override(company_repo):
    service = LogoService(company_repo)
    assert await service.resolve("XYZW3", None) is None
