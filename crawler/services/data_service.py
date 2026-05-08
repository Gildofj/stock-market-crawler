from loguru import logger
from sqlalchemy.orm import Session

from ..models.models import Company, Fundamental, StockPrice
from ..models.schemas import CompanySchema, FundamentalSchema, StockPriceSchema


class DataService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_company(self, company_data: CompanySchema) -> Company:
        company = self.db.query(Company).filter(Company.symbol == company_data.symbol).first()
        if not company:
            company = Company(**company_data.model_dump())
            self.db.add(company)
            self.db.commit()
            self.db.refresh(company)
        return company

    def get_company_by_symbol(self, symbol: str) -> Company:
        return self.db.query(Company).filter(Company.symbol == symbol).first()

    def save_prices(self, company_id: int, prices: list[StockPriceSchema]):
        for price_data in prices:
            # Check if price already exists for this time and company
            existing = (
                self.db.query(StockPrice)
                .filter(StockPrice.time == price_data.time, StockPrice.company_id == company_id)
                .first()
            )

            if not existing:
                price = StockPrice(company_id=company_id, **price_data.model_dump())
                self.db.add(price)

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving prices: {e}")

    def save_fundamentals(self, company_id: int, fundamentals_data: FundamentalSchema):
        fundamental = Fundamental(company_id=company_id, **fundamentals_data.model_dump())
        self.db.add(fundamental)
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving fundamentals: {e}")
