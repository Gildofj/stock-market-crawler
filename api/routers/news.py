import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from api.deps import DBDep
from api.limiter import DefaultRateLimit
from crawler.models.models import Company, LakeNews, LakeNewsTicker

router = APIRouter(
    prefix="/news",
    tags=["News"],
    dependencies=[Depends(DefaultRateLimit)],
)

class NewsItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source: str
    title: str
    url: str
    published_at: datetime | None = None
    summary: str | None = None
    sentiment: str | None = None
    impact: str | None = None

@router.get("/{company_id}", response_model=list[NewsItemSchema])
async def get_news_by_company_id(
    company_id: uuid.UUID,
    db: DBDep,
    limit: Annotated[int, Query(gt=0, le=100)] = 10,
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    news_rows = (
        db.query(LakeNews)
        .join(LakeNewsTicker)
        .filter(LakeNewsTicker.ticker == company.symbol)
        .order_by(LakeNews.published_at.desc())
        .limit(limit)
        .all()
    )

    return [
        NewsItemSchema(
            id=row.id,
            source=row.source,
            title=row.title,
            summary=row.summary,
            url=row.url,
            published_at=row.published_at,
            sentiment=row.sentiment,
            impact=None,
        )
        for row in news_rows
    ]

