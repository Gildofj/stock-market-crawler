from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..deps import get_db
from ..schemas import StockPriceRead
from crawler.models.models import Company, StockPrice
from fastapi_cache.decorator import cache
from fastapi_limiter.depends import RateLimiter

router = APIRouter(prefix="/prices", tags=["Prices"])

@router.get("/{symbol}", response_model=List[StockPriceRead], dependencies=[Depends(RateLimiter(times=20, seconds=60))])
@cache(expire=3600) # Cache de 1 hora para preços
async def get_prices(symbol: str, limit: int = 100, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.symbol == symbol.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    prices = db.query(StockPrice).filter(
        StockPrice.company_id == company.id
    ).order_by(StockPrice.time.desc()).limit(limit).all()
    
    return prices
