import uuid

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import Company, Fundamental, StockPrice
from ..models.schemas import CompanySchema, FundamentalSchema, StockPriceSchema


class DataService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_company(self, company_data: CompanySchema) -> Company:
        try:
            company = self.db.query(Company).filter(Company.symbol == company_data.symbol).first()
            if not company:
                company = Company(**company_data.model_dump())
                self.db.add(company)
            else:
                # Update existing company with better info if available.
                # Special case: if name is just the symbol, always update it.
                updates = company_data.model_dump(exclude={"symbol"})
                for key, value in updates.items():
                    if value is not None:
                        current_val = getattr(company, key)
                        if key == "name":
                            is_symbol = current_val.upper() == company.symbol.upper()
                            if not current_val or is_symbol:
                                if value.upper() != company.symbol.upper():
                                    logger.info(
                                        f"Enriching name for {company.symbol}: "
                                        f"{current_val} -> {value}"
                                    )
                                    setattr(company, key, value)
                        else:
                            if value:
                                setattr(company, key, value)

            self.db.commit()
            self.db.refresh(company)
            return company
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in get_or_create_company for {company_data.symbol}: {e}")
            # Try to return existing if commit failed due to race condition
            return self.db.query(Company).filter(Company.symbol == company_data.symbol).first()

    def get_company_by_symbol(self, symbol: str) -> Company:
        try:
            return self.db.query(Company).filter(Company.symbol == symbol).first()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error fetching company {symbol}: {e}")
            return None

    def update_company_info(self, symbol: str, updates: dict):
        """
        Updates specific company metadata (e.g., logo_url, website).
        """
        try:
            company = self.db.query(Company).filter(Company.symbol == symbol).first()
            if company:
                for key, value in updates.items():
                    if hasattr(company, key) and value is not None:
                        setattr(company, key, value)
                self.db.commit()
                logger.info(f"Updated metadata for {symbol}: {list(updates.keys())}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating company info for {symbol}: {e}")

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
            val['company_id'] = company_id
            values.append(val)

        # Bulk insert with conflict handling (Idempotency)
        stmt = insert(StockPrice).values(values)
        stmt = stmt.on_conflict_do_nothing(index_elements=['time', 'company_id'])

        try:
            self.db.execute(stmt)
            self.db.commit()
            logger.info(f"Bulk saved {len(prices)} prices for company_id {company_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in bulk save_prices for {company_id}: {e}")

    def save_fundamentals(self, company_id: uuid.UUID, fundamentals_data: FundamentalSchema):
        """
        Saves fundamentals ensuring idempotency by checking for recent data.
        """
        # Avoid redundant saves if we already collected fundamentals today
        today = func.current_date()
        existing = self.db.query(Fundamental).filter(
            Fundamental.company_id == company_id,
            func.date(Fundamental.collected_at) == today
        ).first()

        if existing:
            return

        fundamental = Fundamental(company_id=company_id, **fundamentals_data.model_dump())
        self.db.add(fundamental)
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving fundamentals: {e}")
