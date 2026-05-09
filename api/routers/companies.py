from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..deps import get_db
from ..schemas import CompanyRead
from crawler.models.models import Company
from fastapi_cache.decorator import cache
from fastapi_limiter.depends import RateLimiter

router = APIRouter(prefix="/companies", tags=["Companies"])

@router.get("/", response_model=List[CompanyRead], dependencies=[Depends(RateLimiter(times=10, seconds=60))])
@cache(expire=86400) # 24 horas
async def list_companies(db: Session = Depends(get_db)):
    """
    Retorna a lista de todas as empresas cadastradas no sistema.
    """
    return db.query(Company).filter(Company.is_active == 1).all()

@router.get("/{symbol}", response_model=CompanyRead, dependencies=[Depends(RateLimiter(times=20, seconds=60))])
@cache(expire=86400)
async def get_company(symbol: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.symbol == symbol.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
