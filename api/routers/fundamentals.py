import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi_cache.decorator import cache

from api.deps import FundamentalRepoDep
from api.limiter import DefaultRateLimit
from crawler.models.schemas import FundamentalSchema

router = APIRouter(
    prefix="/fundamentals",
    tags=["Fundamentals"],
    dependencies=[Depends(DefaultRateLimit)],
)


@router.get("/{company_id}", response_model=FundamentalSchema)
@cache(expire=3600, namespace="fundamentals:latest")
async def get_latest_fundamentals(company_id: uuid.UUID, repo: FundamentalRepoDep):
    """
    Retrieves the most recent fundamental indicators for a company by its internal ID.
    """
    fundamentals = repo.get_latest(company_id)

    if not fundamentals:
        raise HTTPException(status_code=404, detail="No fundamental data found for this company")

    return fundamentals
