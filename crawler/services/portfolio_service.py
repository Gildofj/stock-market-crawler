import io
import uuid

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session, joinedload

from ..models.models import Portfolio, PortfolioAsset
from ..models.schemas import PortfolioAssetInput


def is_valid_ticker(value: str) -> bool:
    """Brazilian B3 ticker heuristic — matches crawler/services/ticker_service.py."""
    return bool(value) and value.isalnum() and 4 <= len(value) <= 6


class PortfolioParseError(ValueError):
    """Raised when a spreadsheet cannot be parsed into portfolio assets."""


class PortfolioService:
    REQUIRED_COLUMNS = {"ticker", "quantity", "avg_price"}

    def __init__(self, db: Session):
        self.db = db

    def create_portfolio(
        self,
        user_id: uuid.UUID,
        name: str,
        assets: list[PortfolioAssetInput],
        source_r2_key: str | None = None,
        source_filename: str | None = None,
        source_content_type: str | None = None,
    ) -> Portfolio:
        portfolio = Portfolio(
            user_id=user_id,
            name=name,
            source_r2_key=source_r2_key,
            source_filename=source_filename,
            source_content_type=source_content_type,
        )
        for asset in assets:
            portfolio.assets.append(
                PortfolioAsset(
                    ticker=asset.ticker.upper(),
                    quantity=asset.quantity,
                    avg_price=asset.avg_price,
                    asset_type=asset.asset_type,
                    notes=asset.notes,
                )
            )
        self.db.add(portfolio)
        try:
            self.db.commit()
            self.db.refresh(portfolio)
            return portfolio
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create portfolio for user {user_id}: {e}")
            raise

    def list_portfolios(self, user_id: uuid.UUID) -> list[Portfolio]:
        return (
            self.db.query(Portfolio)
            .filter(Portfolio.user_id == user_id)
            .options(joinedload(Portfolio.assets))
            .order_by(Portfolio.created_at.desc())
            .all()
        )

    def get_portfolio(
        self, portfolio_id: uuid.UUID, user_id: uuid.UUID
    ) -> Portfolio | None:
        return (
            self.db.query(Portfolio)
            .filter(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
            .options(joinedload(Portfolio.assets))
            .first()
        )

    def delete_portfolio(self, portfolio_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        portfolio = (
            self.db.query(Portfolio)
            .filter(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
            .first()
        )
        if not portfolio:
            return False
        self.db.delete(portfolio)
        self.db.commit()
        return True

    @classmethod
    def parse_spreadsheet(
        cls, content: bytes, filename: str
    ) -> list[PortfolioAssetInput]:
        filename_lower = filename.lower()
        buffer = io.BytesIO(content)
        try:
            if filename_lower.endswith(".csv"):
                df = pd.read_csv(buffer)
            elif filename_lower.endswith((".xlsx", ".xls")):
                df = pd.read_excel(buffer)
            else:
                raise PortfolioParseError(
                    f"Unsupported file type: {filename}. Use .csv or .xlsx."
                )
        except PortfolioParseError:
            raise
        except Exception as e:
            raise PortfolioParseError(f"Could not read spreadsheet: {e}") from e

        df.columns = [str(c).strip().lower() for c in df.columns]
        missing = cls.REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise PortfolioParseError(
                f"Spreadsheet missing required columns: {sorted(missing)}"
            )

        assets: list[PortfolioAssetInput] = []
        # row_num starts at 2 so it matches the spreadsheet line (header is row 1).
        for row_num, (_, row) in enumerate(df.iterrows(), start=2):
            ticker = str(row["ticker"]).strip().upper()
            if not is_valid_ticker(ticker):
                raise PortfolioParseError(
                    f"Invalid ticker '{ticker}' at row {row_num}"
                )
            try:
                quantity = float(row["quantity"])  # type: ignore[arg-type]
                avg_price = float(row["avg_price"])  # type: ignore[arg-type]
            except (TypeError, ValueError) as e:
                raise PortfolioParseError(
                    f"Invalid number at row {row_num}: {e}"
                ) from e
            if quantity <= 0 or avg_price <= 0:
                raise PortfolioParseError(
                    f"Quantity and avg_price must be > 0 at row {row_num}"
                )

            asset_type_raw = row.get("asset_type") if "asset_type" in df.columns else None
            notes_raw = row.get("notes") if "notes" in df.columns else None

            assets.append(
                PortfolioAssetInput(
                    ticker=ticker,
                    quantity=quantity,
                    avg_price=avg_price,
                    asset_type=str(asset_type_raw).strip()
                    if bool(pd.notna(asset_type_raw))
                    else None,
                    notes=str(notes_raw).strip() if bool(pd.notna(notes_raw)) else None,
                )
            )

        if not assets:
            raise PortfolioParseError("Spreadsheet has no valid asset rows.")
        return assets
