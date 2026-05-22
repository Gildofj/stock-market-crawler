"""RISpider must never invoke the deprecated R2 PDF mirror.

The crawl is allowed to *fetch* PDF bytes to extract a text excerpt, but
those bytes must be discarded immediately afterward. Re-introducing a
mirror upload would re-create the "commercial mirror of CVM" exposure the
project explicitly removed.
"""

import pandas as pd
import pytest

from core.services.source_registry import SourceRecord, get_source_registry
from crawler.spiders import ri_spider as ri_spider_module
from crawler.spiders.ri_spider import RISpider


@pytest.fixture(autouse=True)
def stub_source_registry(monkeypatch):
    registry = get_source_registry()
    # Force the registry to consider 'cvm' enabled regardless of DB state.
    fake_record = SourceRecord(
        id="00000000-0000-0000-0000-000000000001",
        slug="cvm",
        display_name="CVM",
        homepage_url="https://dados.cvm.gov.br/",
        tos_url=None,
        license_label="public-domain",
        risk_tier="low",
        enabled=True,
    )
    monkeypatch.setattr(registry, "_by_slug", {"cvm": fake_record}, raising=True)
    monkeypatch.setattr(registry, "_loaded_at", float("inf"), raising=True)
    yield


def test_spider_does_not_import_storage_module():
    """Tightest guard: the spider's source code must not import R2Storage anymore."""
    import inspect

    source = inspect.getsource(ri_spider_module)
    assert "storage_service" not in source, (
        "RISpider should no longer reference storage_service — mirror removed."
    )
    assert "upload_ri_pdf" not in source, "RISpider must not call upload_ri_pdf (deprecated)."


@pytest.mark.asyncio
async def test_spider_skips_when_cvm_disabled(monkeypatch, db_session):
    """Setting enabled=False on the cvm row should short-circuit crawl_recent."""
    from core.repositories import CompanyRepository
    from core.services.lake_service import LakeService

    # Flip the cached registry record to disabled.
    registry = get_source_registry()
    disabled_record = registry._by_slug["cvm"]
    monkeypatch.setattr(
        registry,
        "_by_slug",
        {"cvm": SourceRecord(**{**disabled_record.__dict__, "enabled": False})},
        raising=True,
    )

    spider = RISpider(
        company_repo=CompanyRepository(db_session),
        lake_service=LakeService(db_session),
        request_manager=None,
    )

    # Force the spider to not need a real network call when disabled.
    async def _empty_df(*args, **kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(
        spider,
        "_fetch_index_csv",
        _empty_df,
    )

    persisted = await spider.crawl_recent(days_back=1)
    assert persisted == 0
