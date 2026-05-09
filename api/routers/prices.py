
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi_cache.decorator import cache
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate
from sqlalchemy.orm import Session

from crawler.models.models import Company, StockPrice

from ..deps import get_db
from ..schemas import StockPriceRead

router = APIRouter(prefix="/prices", tags=["Prices"])

# Modern Rate Limiting (v0.2.0+)
# 20 requests per minute
prices_limiter = Limiter(Rate(20, Duration.MINUTE))


@router.get(
    "/{symbol}",
    response_model=list[StockPriceRead],
    dependencies=[Depends(RateLimiter(limiter=prices_limiter))],
)
@cache(expire=3600)  # Cache de 1 hora para preços
async def get_prices(
    symbol: str, limit: int = 100, db: Annotated[Session, Depends(get_db)] = None
):
    company = db.query(Company).filter(Company.symbol == symbol.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    prices = db.query(StockPrice).filter(
        StockPrice.company_id == company.id
    ).order_by(StockPrice.time.desc()).limit(limit).all()

    return prices
