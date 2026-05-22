from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache

from api.deps import ReliabilityRepoDep
from api.limiter import DefaultRateLimit
from api.schemas import ReliabilityResponse

router = APIRouter(
    prefix="/reliability",
    tags=["Reliability"],
    dependencies=[Depends(DefaultRateLimit)],
)


@router.get("/", response_model=list[ReliabilityResponse])
@cache(expire=1800, namespace="reliability:ranking")
async def get_reliability_ranking(
    repo: ReliabilityRepoDep,
    limit: int = Query(100, gt=0, le=500),
    grade: str | None = Query(None, description="Filter by grade: AAA, AA, A, B, C, D"),
):
    return await repo.get_ranking(limit=limit, grade_filter=grade)


@router.get("/{symbol}", response_model=ReliabilityResponse)
@cache(expire=1800, namespace="reliability:detail")
async def get_company_reliability(symbol: str, repo: ReliabilityRepoDep):
    record = await repo.get_by_symbol(symbol)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Reliability não encontrada para {symbol.upper()}",
        )
    return record
