import uuid

from fastapi import APIRouter, Depends, HTTPException

from api.deps import DBDep
from crawler.models.models import Fundamental
from crawler.models.schemas import FundamentalSchema

router = APIRouter(prefix="/fundamentals", tags=["Fundamentals"])


@router.get("/{company_id}", response_model=FundamentalSchema)
async def get_latest_fundamentals(company_id: uuid.UUID, db: DBDep):
    """
    Retrieves the most recent fundamental indicators for a company.
    """
    fundamentals = (
        db.query(Fundamental)
        .filter(Fundamental.company_id == company_id)
        .order_by(Fundamental.collected_at.desc())
        .first()
    )

    if not fundamentals:
        raise HTTPException(status_code=404, detail="No fundamental data found for this company")

    return fundamentals
