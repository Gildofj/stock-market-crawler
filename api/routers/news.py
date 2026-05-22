import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache
from pydantic import BaseModel, ConfigDict

from api.deps import CompanyRepoDep, LakeServiceDep
from api.limiter import DefaultRateLimit

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
@cache(expire=600, namespace="news:by_company")
async def get_news_by_company_id(
    company_id: uuid.UUID,
    repo: CompanyRepoDep,
    lake: LakeServiceDep,
    limit: Annotated[int, Query(gt=0, le=100)] = 10,
) -> list[NewsItemSchema]:
    company = await repo.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    news_rows = await lake.get_news_by_ticker(company.symbol, limit=limit)

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
