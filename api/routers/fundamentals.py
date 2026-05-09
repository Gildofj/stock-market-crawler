from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..deps import get_db
from ..schemas import FundamentalRead
from crawler.models.models import Company, Fundamental
from fastapi_cache.decorator import cache
from fastapi_limiter.depends import RateLimiter

router = APIRouter(prefix="/fundamentals", tags=["Fundamentals"])

@router.get("/{symbol}", response_model=FundamentalRead, dependencies=[Depends(RateLimiter(times=20, seconds=60))])
@cache(expire=86400)
async def get_fundamentals(symbol: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.symbol == symbol.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    fundamentals = db.query(Fundamental).filter(
        Fundamental.company_id == company.id
    ).order_by(Fundamental.collected_at.desc()).first()
    
    if not fundamentals:
        raise HTTPException(status_code=404, detail="Fundamentals not found for this company")
        
    return fundamentals
