import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache
from pydantic import BaseModel, ConfigDict

from api.deps import CompanyRepoDep, LakeServiceDep
from api.limiter import DefaultRateLimit

router = APIRouter(
    prefix="/investor-relations",
    tags=["Investor Relations"],
    dependencies=[Depends(DefaultRateLimit)],
)


class InvestorRelationLink(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    label: str
    url: str
    kind: str
    published_at: date | None = None


@router.get("/{company_id}", response_model=list[InvestorRelationLink])
@cache(expire=1800, namespace="ri:by_company")
async def get_investor_relations_by_company_id(
    company_id: uuid.UUID,
    repo: CompanyRepoDep,
    lake: LakeServiceDep,
    limit: Annotated[int, Query(gt=0, le=100)] = 10,
) -> list[InvestorRelationLink]:
    company = await repo.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    ri_rows = await lake.get_ri_documents_by_ticker(company.symbol, limit=limit)

    return [
        InvestorRelationLink(
            id=row.id,
            label=f"{row.category}: {row.title}" if row.category else row.title,
            url=row.pdf_url or "",
            kind="cvm",
            published_at=row.reference_date,
        )
        for row in ri_rows
    ]
