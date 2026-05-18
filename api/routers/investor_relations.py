import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from api.deps import DBDep
from api.limiter import DefaultRateLimit
from crawler.models.models import Company, LakeRIDocument

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
async def get_investor_relations_by_company_id(
    company_id: uuid.UUID,
    db: DBDep,
    limit: Annotated[int, Query(gt=0, le=100)] = 10,
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    ri_rows = (
        db.query(LakeRIDocument)
        .filter(LakeRIDocument.ticker == company.symbol)
        .order_by(LakeRIDocument.reference_date.desc())
        .limit(limit)
        .all()
    )

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

