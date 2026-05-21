import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache
from pydantic import BaseModel, ConfigDict

from api.deps import PriceRepoDep
from api.limiter import DefaultRateLimit
from core.models.schemas import StockPriceSchema

router = APIRouter(
    prefix="/prices",
    tags=["Prices"],
    dependencies=[Depends(DefaultRateLimit)],
)


class QuoteSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    company_id: uuid.UUID
    price: float
    previous_close: float
    change_abs: float
    change_pct: float
    currency: str = "BRL"
    as_of: datetime
    market_state: str = "CLOSED"


@router.get("/quotes", response_model=list[QuoteSchema])
@cache(expire=300, namespace="prices:quotes_batch")
async def get_quotes_batch(
    repo: PriceRepoDep,
    company_ids: str = Query(..., alias="companyIds"),
):
    try:
        ids = [uuid.UUID(i.strip()) for i in company_ids.split(",")]
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid UUID format") from e

    quotes = []
    for cid in ids:
        prices = await repo.get_history(cid, limit=2)
        if prices:
            current = prices[0]
            prev = prices[1] if len(prices) > 1 else current
            change_abs = float(current.close) - float(prev.close)
            change_pct = (change_abs / float(prev.close) * 100) if float(prev.close) != 0 else 0.0

            quotes.append(
                QuoteSchema(
                    company_id=cid,
                    price=float(current.close),
                    previous_close=float(prev.close),
                    change_abs=change_abs,
                    change_pct=change_pct,
                    as_of=current.time,
                )
            )

    return quotes


@router.get("/quote/{company_id}", response_model=QuoteSchema)
@cache(expire=300, namespace="prices:quote")
async def get_quote(company_id: uuid.UUID, repo: PriceRepoDep):
    prices = await repo.get_history(company_id, limit=2)

    if not prices:
        raise HTTPException(status_code=404, detail="Quote not found")

    current = prices[0]
    prev = prices[1] if len(prices) > 1 else current
    change_abs = float(current.close) - float(prev.close)
    change_pct = (change_abs / float(prev.close) * 100) if float(prev.close) != 0 else 0.0

    return QuoteSchema(
        company_id=company_id,
        price=float(current.close),
        previous_close=float(prev.close),
        change_abs=change_abs,
        change_pct=change_pct,
        as_of=current.time,
    )


@router.get("/{company_id}", response_model=list[StockPriceSchema])
@cache(expire=300, namespace="prices:history")
async def get_stock_prices(
    company_id: uuid.UUID,
    repo: PriceRepoDep,
    limit: Annotated[int, Query(gt=0, le=1000)] = 100,
):
    prices = await repo.get_history(company_id, limit=limit)

    if not prices:
        raise HTTPException(status_code=404, detail="Prices not found")

    return prices
