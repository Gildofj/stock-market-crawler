"""Persistence + queries for the StockPrice aggregate."""

from __future__ import annotations

import uuid

from loguru import logger
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models.models import StockPrice
from ..models.schemas import StockPriceSchema
from ..services.exceptions import DatabaseError


class PriceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_bulk(
        self, company_id: uuid.UUID, prices: list[StockPriceSchema]
    ) -> None:
        """Idempotent bulk upsert: duplicates on (time, company_id) are skipped."""
        if not prices:
            return

        values = []
        for price in prices:
            row = price.model_dump()
            row["company_id"] = company_id
            values.append(row)

        stmt = insert(StockPrice).values(values).on_conflict_do_nothing(
            index_elements=["time", "company_id"]
        )

        try:
            self.db.execute(stmt)
            self.db.commit()
            logger.info(f"Bulk saved {len(prices)} prices for company_id {company_id}")
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Bulk save prices failed for company_id {company_id}: {exc}")
            raise DatabaseError("Failed to persist prices") from exc

    def get_history(
        self, company_id: uuid.UUID, limit: int = 100
    ) -> list[StockPrice]:
        return (
            self.db.query(StockPrice)
            .filter(StockPrice.company_id == company_id)
            .order_by(StockPrice.time.desc())
            .limit(limit)
            .all()
        )
