from fastapi import APIRouter, HTTPException, Query

from api.deps import DBDep
from api.schemas import ReliabilityResponse
from crawler.services.data_service import DataService

router = APIRouter(prefix="/reliability", tags=["Reliability"])


@router.get("/", response_model=list[ReliabilityResponse])
async def get_reliability_ranking(
    db: DBDep,
    limit: int = Query(100, gt=0, le=500),
    grade: str | None = Query(None, description="Filter by grade: AAA, AA, A, B, C, D"),
):
    """Returns companies ranked by reliability score (descending). Optionally filter by grade."""
    data_service = DataService(db)
    return data_service.get_reliability_ranking(limit=limit, grade_filter=grade)


@router.get("/{symbol}", response_model=ReliabilityResponse)
async def get_company_reliability(symbol: str, db: DBDep):
    """Returns the reliability score and grade for a specific company by ticker symbol."""
    data_service = DataService(db)
    record = data_service.get_reliability_by_symbol(symbol)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No reliability data found for {symbol.upper()}",
        )
    return record
