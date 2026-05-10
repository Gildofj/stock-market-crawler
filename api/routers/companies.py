from fastapi import APIRouter, Depends, HTTPException, Query

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


@router.get("/{symbol}", response_model=CompanySchema)
async def get_company(symbol: str, db: DBDep):
    """
    Retrieves a single company profile by its ticker symbol.
    """
    company = db.query(Company).filter(Company.symbol == symbol.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
