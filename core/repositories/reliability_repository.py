from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.models import Company, CompanyReliability


class ReliabilityRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, company_id: uuid.UUID) -> CompanyReliability | None:
        stmt = select(CompanyReliability).filter(CompanyReliability.company_id == company_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_symbol(self, symbol: str) -> CompanyReliability | None:
        stmt = (
            select(CompanyReliability)
            .join(Company, Company.id == CompanyReliability.company_id)
            .filter(Company.symbol == symbol.upper())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_for_companies(
        self, company_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, CompanyReliability]:
        if not company_ids:
            return {}
        stmt = select(CompanyReliability).filter(CompanyReliability.company_id.in_(company_ids))
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return {row.company_id: row for row in rows}

    async def get_ranking(
        self, limit: int = 100, grade_filter: str | None = None
    ) -> list[CompanyReliability]:
        stmt = (
            select(CompanyReliability)
            .filter(CompanyReliability.reliability_score.isnot(None))
            .order_by(CompanyReliability.reliability_score.desc())
        )
        if grade_filter:
            stmt = stmt.filter(CompanyReliability.reliability_grade == grade_filter.upper())

        result = await self.db.execute(stmt.limit(limit))
        return list(result.scalars().all())
