"""Persistence + queries for the Fundamental aggregate."""

from __future__ import annotations

import uuid

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from core.models.models import Fundamental
from core.models.schemas import FundamentalSchema


class FundamentalRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save(self, company_id: uuid.UUID, payload: FundamentalSchema) -> Fundamental:
        """Persist a fresh fundamentals snapshot. Each call is a new row
        (history is append-only, ordered by ``collected_at``)."""
        fundamental = Fundamental(company_id=company_id, **payload.model_dump())
        self.db.add(fundamental)
        try:
            await self.db.commit()
            return fundamental
        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.error(f"Save fundamentals failed for company_id {company_id}: {exc}")
            raise DatabaseError("Failed to persist fundamentals") from exc

    async def get_latest(self, company_id: uuid.UUID) -> Fundamental | None:
        stmt = (
            select(Fundamental)
            .filter(Fundamental.company_id == company_id)
            .order_by(Fundamental.collected_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_latest_for_companies(
        self, company_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Fundamental]:
        """Most recent ``Fundamental`` per company in a single query.

        Uses ``GROUP BY company_id`` + ``MAX(collected_at)`` joined back to
        the source rows — dialect-safe for PostgreSQL (prod) and SQLite
        (tests), unlike ``DISTINCT ON`` or window functions.
        """
        if not company_ids:
            return {}

        latest_sub = (
            select(
                Fundamental.company_id.label("cid"),
                func.max(Fundamental.collected_at).label("max_at"),
            )
            .filter(Fundamental.company_id.in_(company_ids))
            .group_by(Fundamental.company_id)
            .subquery()
        )

        stmt = (
            select(Fundamental)
            .join(
                latest_sub,
                (Fundamental.company_id == latest_sub.c.cid)
                & (Fundamental.collected_at == latest_sub.c.max_at),
            )
        )

        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return {row.company_id: row for row in rows}
