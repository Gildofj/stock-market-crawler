"""Persistence + queries for the Fundamental aggregate."""

from __future__ import annotations

import uuid

from loguru import logger
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models.models import Fundamental
from ..models.schemas import FundamentalSchema
from ..services.exceptions import DatabaseError


class FundamentalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, company_id: uuid.UUID, payload: FundamentalSchema) -> Fundamental:
        """Persist a fresh fundamentals snapshot. Each call is a new row
        (history is append-only, ordered by ``collected_at``)."""
        fundamental = Fundamental(company_id=company_id, **payload.model_dump())
        self.db.add(fundamental)
        try:
            self.db.commit()
            return fundamental
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Save fundamentals failed for company_id {company_id}: {exc}")
            raise DatabaseError("Failed to persist fundamentals") from exc

    def get_latest(self, company_id: uuid.UUID) -> Fundamental | None:
        return (
            self.db.query(Fundamental)
            .filter(Fundamental.company_id == company_id)
            .order_by(Fundamental.collected_at.desc())
            .first()
        )

    def get_latest_for_companies(
        self, company_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Fundamental]:
        """Most recent ``Fundamental`` per company in a single query.

        Uses ``GROUP BY company_id`` + ``MAX(collected_at)`` joined back to
        the source rows — dialect-safe for PostgreSQL (prod) and SQLite
        (tests), unlike ``DISTINCT ON`` or window functions.
        """
        if not company_ids:
            return {}

        latest = (
            self.db.query(
                Fundamental.company_id.label("cid"),
                func.max(Fundamental.collected_at).label("max_at"),
            )
            .filter(Fundamental.company_id.in_(company_ids))
            .group_by(Fundamental.company_id)
            .subquery()
        )

        rows = (
            self.db.query(Fundamental)
            .join(
                latest,
                (Fundamental.company_id == latest.c.cid)
                & (Fundamental.collected_at == latest.c.max_at),
            )
            .all()
        )
        return {row.company_id: row for row in rows}
