from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_

from api.deps import DBDep
from api.limiter import DefaultRateLimit
from crawler.models.models import Company
from crawler.models.schemas import CompanySchema

router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
    dependencies=[Depends(DefaultRateLimit)],
)


@router.get("/", response_model=list[CompanySchema])
async def get_companies(
    db: DBDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, gt=0, le=2000),
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
    Searches for companies by symbol or name with partial matching and fuzzy search.
    Handles typos using PostgreSQL trigram similarity when available.
    """
    # Base query
    query = db.query(Company)

    # Detect dialect to support SQLite in tests
    is_postgres = db.get_bind().dialect.name == "postgresql"

    if is_postgres:
        # PostgreSQL: Use similarity for fuzzy matching (handling typos)
        # We combine substring matching (ilike) with similarity scores
        # Results are ordered by the best match (substring match first, then similarity)
        companies = (
            query.filter(
                or_(
                    Company.symbol.ilike(f"%{q}%"),
                    Company.name.ilike(f"%{q}%"),
                    func.similarity(Company.symbol, q) > 0.3,
                    func.similarity(Company.name, q) > 0.3,
                )
            )
            .order_by(
                # Priority: exact symbol > substring match > similarity
                Company.symbol.ilike(q).desc(),
                Company.symbol.ilike(f"%{q}%").desc(),
                func.similarity(Company.name, q).desc(),
            )
            .limit(limit)
            .all()
        )
    else:
        # Fallback for SQLite (Tests): Only ilike
        companies = (
            query.filter(or_(Company.symbol.ilike(f"%{q}%"), Company.name.ilike(f"%{q}%")))
            .order_by(Company.symbol.ilike(q).desc(), Company.symbol.asc())
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
