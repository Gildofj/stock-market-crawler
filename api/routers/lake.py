from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import DBDep, PremiumUserDep
from api.limiter import DefaultRateLimit, StrictRateLimit
from crawler.models.schemas import (
    FundamentalSchema,
    LakeInsightSchema,
    LakeNewsSchema,
    LakeRIDocumentSchema,
)
from crawler.services.data_service import DataService
from crawler.services.lake_service import LakeService

router = APIRouter(
    prefix="/lake",
    tags=["Data Lake"],
    dependencies=[Depends(DefaultRateLimit)],
)


def _news_to_schema(news_rows) -> list[LakeNewsSchema]:
    return [
        LakeNewsSchema(
            id=row.id,
            source=row.source,
            title=row.title,
            summary=row.summary,
            url=row.url,
            url_hash=row.url_hash,
            sentiment=row.sentiment,
            published_at=row.published_at,
            tickers=[t.ticker for t in row.tickers],
        )
        for row in news_rows
    ]


@router.get("/{symbol}", summary="Aggregated lake snapshot for a ticker")
async def get_lake_snapshot(
    symbol: str,
    db: DBDep,
    user: PremiumUserDep,
):
    """Returns news, RI documents, fundamentals and cached AI insight for a ticker."""
    symbol_u = symbol.upper()
    lake_service = LakeService(db)
    data_service = DataService(db)

    company = data_service.get_company_by_symbol(symbol_u)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {symbol_u} not found")

    news = lake_service.get_news_by_ticker(symbol_u, limit=10)
    ri_docs = lake_service.get_ri_documents_by_ticker(symbol_u, limit=3)
    fundamentals = data_service.get_latest_fundamentals(company.id)
    cache = lake_service.get_insight_cache(symbol_u)

    return {
        "ticker": symbol_u,
        "company_id": company.id,
        "news": _news_to_schema(news),
        "ri_documents": [
            LakeRIDocumentSchema.model_validate(doc) for doc in ri_docs
        ],
        "fundamentals": FundamentalSchema.model_validate(fundamentals)
        if fundamentals
        else None,
        "insight": LakeInsightSchema.model_validate(cache) if cache else None,
    }


@router.get(
    "/{symbol}/news",
    response_model=list[LakeNewsSchema],
    summary="News feed for a ticker",
)
async def get_lake_news(
    symbol: str,
    db: DBDep,
    user: PremiumUserDep,
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
):
    lake_service = LakeService(db)
    rows = lake_service.get_news_by_ticker(symbol.upper(), limit=limit, offset=offset)
    return _news_to_schema(rows)


@router.get(
    "/{symbol}/ri",
    response_model=list[LakeRIDocumentSchema],
    summary="Latest RI documents for a ticker",
)
async def get_lake_ri(
    symbol: str,
    db: DBDep,
    user: PremiumUserDep,
    limit: int = Query(5, gt=0, le=20),
):
    lake_service = LakeService(db)
    return lake_service.get_ri_documents_by_ticker(symbol.upper(), limit=limit)


@router.post(
    "/{symbol}/insight",
    response_model=LakeInsightSchema,
    summary="Upsert AI insight cache (service-to-service)",
    dependencies=[Depends(StrictRateLimit)],
)
async def upsert_lake_insight(
    symbol: str,
    payload: LakeInsightSchema,
    db: DBDep,
    ttl_hours: int = Query(6, gt=0, le=72),
):
    """Allows the AI Gateway to push a fresh insight payload into the cache.

    Protected by the API key only (no premium gating) so trusted backend
    services can refresh the cache.
    """
    lake_service = LakeService(db)
    payload_with_ticker = payload.model_copy(update={"ticker": symbol.upper()})
    cache = lake_service.upsert_insight_cache(
        symbol.upper(), payload_with_ticker, ttl_hours=ttl_hours
    )
    return LakeInsightSchema.model_validate(cache)
