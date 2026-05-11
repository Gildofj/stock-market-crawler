import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import DBDep
from crawler.models.models import StockPrice
from crawler.models.schemas import StockPriceSchema

router = APIRouter(prefix="/prices", tags=["Prices"])


@router.get("/{company_id}", response_model=list[StockPriceSchema])
async def get_stock_prices(
    company_id: uuid.UUID,
    db: DBDep,
    limit: Annotated[int, Query(gt=0, le=1000)] = 100,
):
    """
    Retrieves historical price data for a specific company by its internal ID.
    """
    prices = (
        db.query(StockPrice)
        .filter(StockPrice.company_id == company_id)
        .order_by(StockPrice.time.desc())
        .limit(limit)
        .all()
    )

    if not prices:
        raise HTTPException(status_code=404, detail="No prices found for this company")

    return prices
