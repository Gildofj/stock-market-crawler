import uuid
from decimal import Decimal

import pandas as pd
from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import Company, Fundamental, MLFeature, StockPrice
from ..models.schemas import CompanySchema, FundamentalSchema, StockPriceSchema


class DataService:
    def __init__(self, db: Session):
        self.db = db

    def get_company_by_symbol(self, symbol: str) -> Company | None:
        return self.db.query(Company).filter(Company.symbol == symbol).first()

    def get_or_create_company(self, company_data: CompanySchema) -> Company:
        """
        Retrieves a company by symbol or creates it if it doesn't exist.
        """
        company = (
            self.db.query(Company).filter(Company.symbol == company_data.symbol).first()
        )

        if not company:
            company = Company(**company_data.model_dump())
            self.db.add(company)
            self.db.commit()
            self.db.refresh(company)

        # Update existing company with fresh metadata if provided
        else:
            updated = False
            for field, value in company_data.model_dump(exclude_unset=True).items():
                if getattr(company, field) != value:
                    setattr(company, field, value)
                    updated = True
            if updated:
                self.db.commit()

        if company is None:
            raise ValueError(f"Failed to retrieve or create company: {company_data.symbol}")

        return company

    def update_company_info(self, symbol: str, data: dict):
        company = self.get_company_by_symbol(symbol)
        if company:
            for key, value in data.items():
                setattr(company, key, value)
            self.db.commit()

    def save_prices(self, company_id: uuid.UUID, prices: list[StockPriceSchema]):
        """
        Saves prices using bulk insert logic for maximum performance.
        """
        if not prices:
            return

        from sqlalchemy.dialects.postgresql import insert

        values = []
        for p in prices:
            val = p.model_dump()
            val["company_id"] = company_id
            values.append(val)

        stmt = insert(StockPrice).values(values)
        # Handle conflicts (idempotency) by doing nothing on duplicate timestamp/company
        stmt = stmt.on_conflict_do_nothing(index_elements=["time", "company_id"])

        try:
            self.db.execute(stmt)
            self.db.commit()
            logger.info(f"Bulk saved {len(prices)} prices for company_id {company_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk saving prices: {e}")

    def save_fundamentals(self, company_id: uuid.UUID, fundamentals_data: FundamentalSchema):
        """
        Saves a new fundamental data record.
        """
        fundamental = Fundamental(company_id=company_id, **fundamentals_data.model_dump())
        self.db.add(fundamental)
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving fundamentals: {e}")

    def get_latest_fundamentals(self, company_id: uuid.UUID) -> Fundamental | None:
        return (
            self.db.query(Fundamental)
            .filter(Fundamental.company_id == company_id)
            .order_by(Fundamental.collected_at.desc())
            .first()
        )

    def get_price_history(self, company_id: uuid.UUID, limit: int = 100) -> list[StockPrice]:
        return (
            self.db.query(StockPrice)
            .filter(StockPrice.company_id == company_id)
            .order_by(StockPrice.time.desc())
            .limit(limit)
            .all()
        )
