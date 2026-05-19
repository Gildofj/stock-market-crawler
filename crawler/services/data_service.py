import uuid

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import Company, CompanyReliability, Fundamental, StockPrice
from ..models.schemas import CompanySchema, FundamentalSchema, StockPriceSchema


class DataService:
    def __init__(self, db: Session):
        self.db = db

    def get_company_by_symbol(self, symbol: str) -> Company | None:
        return self.db.query(Company).filter(Company.symbol == symbol).first()

    def get_all_known_symbols(self) -> set[str]:
        """
        Returns the set of every symbol persisted in the companies table.

        Used by spiders that need to detect mentions of known tickers in free text.
        """
        rows = self.db.query(Company.symbol).all()
        return {row[0] for row in rows}

    def get_existing_symbols(self, symbols: list[str]) -> set[str]:
        """
        Returns the set of symbols that already exist in the database.

        Single bulk query — avoids one round-trip per ticker in batch workflows.
        """
        if not symbols:
            return set()
        rows = (
            self.db.query(Company.symbol).filter(Company.symbol.in_(symbols)).all()
        )
        return {row[0] for row in rows}

    def get_or_create_company(self, company_data: CompanySchema) -> Company:
        """
        Retrieves a company by symbol or creates it if it doesn't exist.
        """
        company = self.db.query(Company).filter(Company.symbol == company_data.symbol).first()

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

    def get_reliability(self, company_id: uuid.UUID) -> CompanyReliability | None:
        return (
            self.db.query(CompanyReliability)
            .filter(CompanyReliability.company_id == company_id)
            .first()
        )

    def get_reliability_by_symbol(self, symbol: str) -> CompanyReliability | None:
        return (
            self.db.query(CompanyReliability)
            .join(Company, Company.id == CompanyReliability.company_id)
            .filter(Company.symbol == symbol.upper())
            .first()
        )

    def get_companies_by_symbols(self, symbols: list[str]) -> list[Company]:
        """Single `.in_()` lookup for the batch portfolio snapshot endpoint."""
        if not symbols:
            return []
        return (
            self.db.query(Company)
            .filter(Company.symbol.in_(symbols))
            .all()
        )

    def get_latest_fundamentals_for_companies(
        self, company_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Fundamental]:
        """Latest Fundamental per company in a single query.

        Uses a `GROUP BY company_id` + `MAX(collected_at)` subquery joined
        back to the row — dialect-safe for PostgreSQL (prod) and SQLite
        (tests), unlike `DISTINCT ON` or window functions which would tie
        us to Postgres.
        """
        if not company_ids:
            return {}
        latest_subq = (
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
                latest_subq,
                (Fundamental.company_id == latest_subq.c.cid)
                & (Fundamental.collected_at == latest_subq.c.max_at),
            )
            .all()
        )
        return {row.company_id: row for row in rows}

    def get_reliability_for_companies(
        self, company_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, CompanyReliability]:
        """Single `.in_()` lookup — relies on the unique(company_id) constraint."""
        if not company_ids:
            return {}
        rows = (
            self.db.query(CompanyReliability)
            .filter(CompanyReliability.company_id.in_(company_ids))
            .all()
        )
        return {row.company_id: row for row in rows}

    def get_reliability_ranking(
        self,
        limit: int = 100,
        grade_filter: str | None = None,
    ) -> list[CompanyReliability]:
        query = (
            self.db.query(CompanyReliability)
            .filter(CompanyReliability.reliability_score.isnot(None))
            .order_by(CompanyReliability.reliability_score.desc())
        )
        if grade_filter:
            query = query.filter(CompanyReliability.reliability_grade == grade_filter.upper())
        return query.limit(limit).all()
