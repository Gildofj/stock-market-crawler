from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache

from api.deps import (
    CompanyRepoDep,
    FundamentalRepoDep,
    LakeServiceDep,
)
from api.limiter import DefaultRateLimit, StrictRateLimit
from core.models.schemas import (
    FundamentalSchema,
    LakeInsightSchema,
    LakeNewsSchema,
    LakeRIDocumentSchema,
)

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
@cache(expire=600, namespace="lake:snapshot")
async def get_lake_snapshot(
    symbol: str,
    repo: CompanyRepoDep,
    fundamental_repo: FundamentalRepoDep,
    lake: LakeServiceDep,
):
    """Returns news, RI documents, fundamentals and cached AI insight for a ticker."""
    symbol_u = symbol.upper()

    company = await repo.get_by_symbol(symbol_u)
    if not company:
        raise HTTPException(status_code=404, detail=f"Empresa {symbol_u} não encontrada")

    news = await lake.get_news_by_ticker(symbol_u, limit=10)
    ri_docs = await lake.get_ri_documents_by_ticker(symbol_u, limit=3)
    fundamentals = await fundamental_repo.get_latest(company.id)
    cache_row = await lake.get_insight_cache(symbol_u)

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
        "insight": LakeInsightSchema.model_validate(cache_row) if cache_row else None,
    }


@router.get(
    "/{symbol}/news",
    response_model=list[LakeNewsSchema],
    summary="News feed for a ticker",
)
@cache(expire=600, namespace="lake:news")
async def get_lake_news(
    symbol: str,
    lake: LakeServiceDep,
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
):
    rows = await lake.get_news_by_ticker(symbol.upper(), limit=limit, offset=offset)
    return _news_to_schema(rows)


@router.get(
    "/{symbol}/ri",
    response_model=list[LakeRIDocumentSchema],
    summary="Latest RI documents for a ticker",
)
@cache(expire=600, namespace="lake:ri")
async def get_lake_ri(
    symbol: str,
    lake: LakeServiceDep,
    limit: int = Query(5, gt=0, le=20),
):
    return await lake.get_ri_documents_by_ticker(symbol.upper(), limit=limit)


@router.post(
    "/{symbol}/insight",
    response_model=LakeInsightSchema,
    summary="Upsert AI insight cache (service-to-service)",
    dependencies=[Depends(StrictRateLimit)],
)
async def upsert_lake_insight(
    symbol: str,
    payload: LakeInsightSchema,
    lake: LakeServiceDep,
    ttl_hours: int = Query(6, gt=0, le=72),
):
    """Allows the AI Gateway to push a fresh insight payload into the cache.

    Protected by the API key only (no premium gating) so trusted backend
    services can refresh the cache.
    """
    payload_with_ticker = payload.model_copy(update={"ticker": symbol.upper()})
    cache_row = await lake.upsert_insight_cache(
        symbol.upper(), payload_with_ticker, ttl_hours=ttl_hours
    )
    return LakeInsightSchema.model_validate(cache_row)
