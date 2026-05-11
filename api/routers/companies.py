from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_

from api.deps import DBDep
from crawler.models.models import Company
from crawler.models.schemas import CompanySchema

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/", response_model=list[CompanySchema])
async def get_companies(
    db: DBDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=500),
):
    """
    Lists all tracked companies with pagination.
    """
    companies = db.query(Company).offset(skip).limit(limit).all()
    return companies


@router.get("/search", response_model=list[CompanySchema])
async def search_companies(
    db: DBDep,
    q: str = Query(..., min_length=1, description="Search term for symbol or name"),
    limit: int = Query(10, gt=0, le=50, description="Maximum number of results to return"),
):
    """
    Searches for companies by symbol or name with partial matching.
    Designed for frontend selectors/autocomplete.
    """
    companies = (
        db.query(Company)
        .filter(or_(Company.symbol.ilike(f"%{q}%"), Company.name.ilike(f"%{q}%")))
        .limit(limit)
        .all()
    )
    return companies


@router.get("/{symbol}", response_model=CompanySchema)
async def get_company(symbol: str, db: DBDep):
    """
    Retrieves a single company profile by its ticker symbol.
    """
    company = db.query(Company).filter(Company.symbol == symbol.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
