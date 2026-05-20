"""Queries for the CompanyReliability aggregate.

Writes live in ``crawler/services/reliability_service.py`` because they
require composing reliability scores from multiple sources — this repo only
exposes lookups.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..models.models import Company, CompanyReliability


class ReliabilityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, company_id: uuid.UUID) -> CompanyReliability | None:
        return (
            self.db.query(CompanyReliability)
            .filter(CompanyReliability.company_id == company_id)
            .first()
        )

    def get_by_symbol(self, symbol: str) -> CompanyReliability | None:
        return (
            self.db.query(CompanyReliability)
            .join(Company, Company.id == CompanyReliability.company_id)
            .filter(Company.symbol == symbol.upper())
            .first()
        )

    def get_for_companies(
        self, company_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, CompanyReliability]:
        """Bulk lookup leveraging the ``UNIQUE(company_id)`` constraint."""
        if not company_ids:
            return {}
        rows = (
            self.db.query(CompanyReliability)
            .filter(CompanyReliability.company_id.in_(company_ids))
            .all()
        )
        return {row.company_id: row for row in rows}

    def get_ranking(
        self, limit: int = 100, grade_filter: str | None = None
    ) -> list[CompanyReliability]:
        query = (
            self.db.query(CompanyReliability)
            .filter(CompanyReliability.reliability_score.isnot(None))
            .order_by(CompanyReliability.reliability_score.desc())
        )
        if grade_filter:
            query = query.filter(
                CompanyReliability.reliability_grade == grade_filter.upper()
            )
        return query.limit(limit).all()
