import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from core.database import get_db as get_crawler_db
from core.models.models import (
    Company,
    CompanyReliability,
    Fundamental,
    LakeNews,
    LakeNewsTicker,
)
from tests.conftest import TEST_AUTH_HEADERS

client = TestClient(app, headers=TEST_AUTH_HEADERS)


@pytest.fixture
def override_db(db_session: AsyncSession):
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_crawler_db] = _override_db
    yield db_session
    app.dependency_overrides.clear()


async def _seed_company(db: AsyncSession, symbol: str, name: str | None = None) -> Company:
    company = Company(symbol=symbol, name=name or f"{symbol} Co", sector="Test")
    db.add(company)
    await db.flush()
    return company


async def _seed_fundamental(
    db: AsyncSession,
    company_id: uuid.UUID,
    p_l: float = 10.0,
    collected_at: datetime | None = None,
) -> Fundamental:
    fundamental = Fundamental(
        company_id=company_id,
        p_l=p_l,
        collected_at=collected_at or datetime.now(UTC),
    )
    db.add(fundamental)
    await db.flush()
    return fundamental


async def _seed_reliability(
    db: AsyncSession,
    company_id: uuid.UUID,
    score: int = 85,
    grade: str = "A",
) -> CompanyReliability:
    reliability = CompanyReliability(
        company_id=company_id,
        reliability_score=score,
        reliability_grade=grade,
    )
    db.add(reliability)
    await db.flush()
    return reliability


async def _seed_news(
    db: AsyncSession,
    tickers: list[str],
    url_hash: str,
    published_at: datetime | None = None,
    title: str = "Headline",
) -> LakeNews:
    news = LakeNews(
        source="test-feed",
        title=title,
        url=f"https://news.example/{url_hash}",
        url_hash=url_hash,
        published_at=published_at or datetime.now(UTC),
    )
    for ticker in tickers:
        news.tickers.append(LakeNewsTicker(ticker=ticker))
    db.add(news)
    await db.flush()
    return news


# --- input validation -------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_rejects_empty_symbols(override_db):
    response = client.get("/api/v1/portfolio/snapshot?symbols=")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_snapshot_rejects_missing_symbols_param(override_db):
    response = client.get("/api/v1/portfolio/snapshot")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_snapshot_rejects_over_50_symbols(override_db):
    symbols = ",".join(f"TKR{i:03d}" for i in range(51))
    response = client.get(f"/api/v1/portfolio/snapshot?symbols={symbols}")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_snapshot_requires_api_key(override_db):
    bare_client = TestClient(app)
    response = bare_client.get("/api/v1/portfolio/snapshot?symbols=PETR4")
    assert response.status_code == 401


# --- happy path -------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_returns_all_sections_for_known_symbols(
    db_session: AsyncSession, override_db
):
    petr = await _seed_company(db_session, "PETR4", "Petrobras PN")
    vale = await _seed_company(db_session, "VALE3", "Vale ON")

    await _seed_fundamental(db_session, petr.id, p_l=4.5)
    await _seed_fundamental(db_session, vale.id, p_l=6.1)
    await _seed_reliability(db_session, petr.id, score=92, grade="AAA")
    await _seed_reliability(db_session, vale.id, score=78, grade="A")

    for i in range(12):
        await _seed_news(
            db_session,
            tickers=["PETR4"],
            url_hash=f"petr-{i}",
            published_at=datetime.now(UTC) - timedelta(hours=i),
            title=f"PETR headline {i}",
        )

    await db_session.commit()

    response = client.get("/api/v1/portfolio/snapshot?symbols=PETR4,VALE3&news_per_symbol=10")
    assert response.status_code == 200
    body = response.json()

    assert body["requested"] == 2
    assert body["found"] == 2
    assert body["missing"] == []
    assert len(body["items"]) == 2

    petr_item, vale_item = body["items"]
    assert petr_item["symbol"] == "PETR4"
    assert petr_item["found"] is True
    assert petr_item["company"]["name"] == "Petrobras PN"
    assert petr_item["fundamentals"]["p_l"] == "4.50"
    assert petr_item["reliability"]["reliability_grade"] == "AAA"
    assert len(petr_item["news"]) == 10
    titles = [n["title"] for n in petr_item["news"]]
    # news are returned by published_at desc, and seed loop creates them with increasing offset.
    # So index 0 is newest (PETR headline 0), index 9 is oldest (PETR headline 9).
    assert titles[0] == "PETR headline 0"

    assert vale_item["symbol"] == "VALE3"
    assert vale_item["found"] is True
    assert vale_item["news"] == []


@pytest.mark.asyncio
async def test_snapshot_marks_unknown_symbols_with_found_false(
    db_session: AsyncSession, override_db
):
    await _seed_company(db_session, "PETR4")
    await db_session.commit()

    response = client.get("/api/v1/portfolio/snapshot?symbols=PETR4,XPTO4")
    assert response.status_code == 200
    body = response.json()

    assert body["requested"] == 2
    assert body["found"] == 1
    assert body["missing"] == ["XPTO4"]
    assert body["items"][0]["found"] is True
    assert body["items"][1]["found"] is False
    assert body["items"][1]["company"] is None


@pytest.mark.asyncio
async def test_snapshot_all_unknown_returns_400(db_session: AsyncSession, override_db):
    response = client.get("/api/v1/portfolio/snapshot?symbols=AAA1,BBB2")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_snapshot_deduplicates_and_uppercases(db_session: AsyncSession, override_db):
    await _seed_company(db_session, "PETR4")
    await _seed_company(db_session, "VALE3")
    await db_session.commit()

    response = client.get("/api/v1/portfolio/snapshot?symbols=petr4,PETR4,vale3")
    assert response.status_code == 200
    body = response.json()

    assert body["requested"] == 2
    assert [item["symbol"] for item in body["items"]] == ["PETR4", "VALE3"]


@pytest.mark.asyncio
async def test_snapshot_news_shared_across_tickers_in_request_appears_in_both_buckets(
    db_session: AsyncSession, override_db
):
    await _seed_company(db_session, "PETR4")
    await _seed_company(db_session, "VALE3")
    await _seed_news(db_session, tickers=["PETR4", "VALE3"], url_hash="shared-1")
    await db_session.commit()

    response = client.get("/api/v1/portfolio/snapshot?symbols=PETR4,VALE3")
    assert response.status_code == 200
    body = response.json()

    petr_news = body["items"][0]["news"]
    vale_news = body["items"][1]["news"]
    assert len(petr_news) == 1
    assert len(vale_news) == 1
    assert petr_news[0]["url_hash"] == "shared-1"
    assert vale_news[0]["url_hash"] == "shared-1"


@pytest.mark.asyncio
async def test_snapshot_handles_company_with_no_fundamentals(db_session: AsyncSession, override_db):
    await _seed_company(db_session, "PETR4")
    await db_session.commit()

    response = client.get("/api/v1/portfolio/snapshot?symbols=PETR4")
    assert response.status_code == 200
    item = response.json()["items"][0]

    assert item["found"] is True
    assert item["fundamentals"] is None
    assert item["reliability"] is None
    assert item["news"] == []


@pytest.mark.asyncio
async def test_snapshot_returns_only_latest_fundamental_per_company(
    db_session: AsyncSession, override_db
):
    petr = await _seed_company(db_session, "PETR4")
    older = datetime.now(UTC) - timedelta(days=30)
    newer = datetime.now(UTC)
    await _seed_fundamental(db_session, petr.id, p_l=8.0, collected_at=older)
    await _seed_fundamental(db_session, petr.id, p_l=4.2, collected_at=newer)
    await db_session.commit()

    response = client.get("/api/v1/portfolio/snapshot?symbols=PETR4")
    assert response.status_code == 200
    assert response.json()["items"][0]["fundamentals"]["p_l"] == "4.20"


# --- regression: query budget ----------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_issues_constant_query_count(db_session: AsyncSession, override_db, engine):
    """N+1 regression net. The endpoint must issue exactly four bulk
    queries (companies, fundamentals, reliability, news) regardless of
    how many symbols are requested.
    """
    for i in range(5):
        company = await _seed_company(db_session, f"TST{i}A")
        await _seed_fundamental(db_session, company.id, p_l=float(10 + i))
        await _seed_reliability(db_session, company.id, score=80 + i, grade="A")
        await _seed_news(db_session, tickers=[f"TST{i}A"], url_hash=f"news-{i}")
    await db_session.commit()

    captured: list[str] = []

    def _record(conn, cursor, statement, params, context, executemany):
        captured.append(statement)

    # engine is AsyncEngine, need to access the underlying sync engine for events
    sync_engine = engine.sync_engine
    event.listen(sync_engine, "before_cursor_execute", _record)
    try:
        captured.clear()
        symbols = ",".join(f"TST{i}A" for i in range(5))
        response = client.get(f"/api/v1/portfolio/snapshot?symbols={symbols}")
        assert response.status_code == 200
        select_statements = [s for s in captured if s.strip().upper().startswith("SELECT")]
    finally:
        event.remove(sync_engine, "before_cursor_execute", _record)

    assert len(select_statements) <= 5, (
        f"Expected ≤ 5 SELECTs (N+1 regression), got "
        f"{len(select_statements)}:\n" + "\n---\n".join(select_statements)
    )
