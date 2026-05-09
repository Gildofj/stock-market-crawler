
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi_cache.decorator import cache
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate
from sqlalchemy.orm import Session

from crawler.models.models import Company

from ..deps import get_db
from ..schemas import CompanyRead

router = APIRouter(prefix="/companies", tags=["Companies"])

# Modern Rate Limiting (v0.2.0+)
# 10 requests per minute
list_limiter = Limiter(Rate(10, Duration.MINUTE))
# 20 requests per minute
detail_limiter = Limiter(Rate(20, Duration.MINUTE))


@router.get(
    "/",
    response_model=list[CompanyRead],
    dependencies=[Depends(RateLimiter(limiter=list_limiter))],
)
@cache(expire=86400)  # 24 horas
async def list_companies(db: Annotated[Session, Depends(get_db)]):
    """
    Retorna a lista de todas as empresas cadastradas no sistema.
    """
    return db.query(Company).filter(Company.is_active == 1).all()


@router.get(
    "/{symbol}",
    response_model=CompanyRead,
    dependencies=[Depends(RateLimiter(limiter=detail_limiter))],
)
@cache(expire=86400)
async def get_company(symbol: str, db: Annotated[Session, Depends(get_db)]):
    company = db.query(Company).filter(Company.symbol == symbol.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
