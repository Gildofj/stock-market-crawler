from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache

from api.deps import CompanyRepoDep
from api.limiter import DefaultRateLimit
from core.models.schemas import CompanySchema

router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
    dependencies=[Depends(DefaultRateLimit)],
)


@router.get("/", response_model=list[CompanySchema])
@cache(expire=1800, namespace="companies:list")
async def get_companies(
    repo: CompanyRepoDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, gt=0, le=2000),
):
    """
    Lists all tracked companies with pagination.
    """
    return await repo.list_paginated(skip=skip, limit=limit)


@router.get("/search", response_model=list[CompanySchema])
@cache(expire=600, namespace="companies:search")
async def search_companies(
    repo: CompanyRepoDep,
    q: str = Query(..., min_length=1, description="Search term for symbol or name"),
    limit: int = Query(10, gt=0, le=50, description="Maximum number of results to return"),
):
    """
    Searches for companies by symbol or name with partial matching and fuzzy search.
    Handles typos using PostgreSQL trigram similarity when available.
    """
    return await repo.search(query=q, limit=limit)


@router.get("/{symbol}", response_model=CompanySchema)
@cache(expire=1800, namespace="companies:detail")
async def get_company(symbol: str, repo: CompanyRepoDep):
    """
    Retrieves a single company profile by its ticker symbol.
    """
    company = await repo.get_by_symbol(symbol.upper())
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
