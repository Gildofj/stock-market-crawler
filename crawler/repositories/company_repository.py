"""Persistence + queries for the Company aggregate."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models.models import Company
from ..models.schemas import CompanySchema


class CompanyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, company_id: uuid.UUID) -> Company | None:
        return self.db.query(Company).filter(Company.id == company_id).first()

    def get_by_symbol(self, symbol: str) -> Company | None:
        return self.db.query(Company).filter(Company.symbol == symbol).first()

    def get_many_by_symbols(self, symbols: list[str]) -> list[Company]:
        """Bulk lookup for the batch portfolio snapshot endpoint."""
        if not symbols:
            return []
        return self.db.query(Company).filter(Company.symbol.in_(symbols)).all()

    def get_all_symbols(self) -> set[str]:
        """Every symbol persisted — used by spiders that need to detect
        mentions of known tickers in free text."""
        rows = self.db.query(Company.symbol).all()
        return {row[0] for row in rows}

    def get_existing_symbols(self, symbols: list[str]) -> set[str]:
        """Subset of ``symbols`` already present — single round-trip."""
        if not symbols:
            return set()
        rows = self.db.query(Company.symbol).filter(Company.symbol.in_(symbols)).all()
        return {row[0] for row in rows}

    def list_paginated(self, skip: int = 0, limit: int = 1000) -> list[Company]:
        return self.db.query(Company).offset(skip).limit(limit).all()

    def search(self, query: str, limit: int = 10) -> list[Company]:
        """Symbol/name search with PostgreSQL trigram fuzzy matching when
        available; falls back to plain ``ilike`` on SQLite (used in tests).

        Ranking priority: exact symbol → substring → trigram similarity.
        """
        is_postgres = self.db.get_bind().dialect.name == "postgresql"
        base = self.db.query(Company)

        if is_postgres:
            return (
                base.filter(
                    or_(
                        Company.symbol.ilike(f"%{query}%"),
                        Company.name.ilike(f"%{query}%"),
                        func.similarity(Company.symbol, query) > 0.3,
                        func.similarity(Company.name, query) > 0.3,
                    )
                )
                .order_by(
                    Company.symbol.ilike(query).desc(),
                    Company.symbol.ilike(f"%{query}%").desc(),
                    func.similarity(Company.name, query).desc(),
                )
                .limit(limit)
                .all()
            )

        return (
            base.filter(
                or_(Company.symbol.ilike(f"%{query}%"), Company.name.ilike(f"%{query}%"))
            )
            .order_by(Company.symbol.ilike(query).desc(), Company.symbol.asc())
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def get_or_create(self, company_data: CompanySchema) -> Company:
        """Returns the existing row or creates one, refreshing metadata when
        the payload differs from what's stored."""
        company = (
            self.db.query(Company).filter(Company.symbol == company_data.symbol).first()
        )

        if company is None:
            company = Company(**company_data.model_dump())
            self.db.add(company)
            self.db.commit()
            self.db.refresh(company)
            return company

        updated = False
        for field, value in company_data.model_dump(exclude_unset=True).items():
            if getattr(company, field) != value:
                setattr(company, field, value)
                updated = True
        if updated:
            self.db.commit()
        return company

    def update_info(self, symbol: str, data: dict) -> None:
        company = self.get_by_symbol(symbol)
        if company is None:
            return
        for key, value in data.items():
            setattr(company, key, value)
        self.db.commit()
