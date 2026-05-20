import uuid
from decimal import Decimal
from typing import Any

import pandas as pd
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.models.models import Fundamental, MLFeature, StockPrice
from core.services.exceptions import DatabaseError


class ETLService:
    def __init__(self, db: Session):
        self.db = db

    def generate_features(self, company_id: uuid.UUID):
        logger.info(f"Generating ML features for company_id: {company_id}")

        # 1. Load data
        prices = (
            self.db.query(StockPrice)
            .filter(StockPrice.company_id == company_id)
            .order_by(StockPrice.time)
            .all()
        )
        if not prices:
            return

        # Fetch latest EPS for fundamental ratio calculations
        latest_fundamental = (
            self.db.query(Fundamental)
            .filter(Fundamental.company_id == company_id)
            .order_by(Fundamental.collected_at.desc())
            .first()
        )

        eps: float | None = None
        if latest_fundamental and latest_fundamental.eps is not None:
            eps = float(latest_fundamental.eps)

        df = pd.DataFrame(
            [{"time": p.time, "close": float(p.close), "volume": p.volume} for p in prices]
        )

        # 2. Calculate Indicators
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["sma_50"] = df["close"].rolling(window=50).mean()

        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi_14"] = 100 - (100 / (1 + rs))

        df["volatility_20"] = df["close"].rolling(window=20).std()

        # Fundamental Ratios
        if eps and eps > 0:
            df["p_l_ratio"] = df["close"] / eps
        else:
            df["p_l_ratio"] = None

        # Target: Percentage change of next day
        df["target_next_day_change"] = df["close"].shift(-1) / df["close"] - 1

        # 3. Save to DB
        # Only drop rows where essential technical indicators or target are missing.
        # Fundamental ratios like p_l_ratio are allowed to be None.
        essential_cols = ["sma_20", "sma_50", "rsi_14", "volatility_20", "target_next_day_change"]

        valid_df = df.dropna(subset=essential_cols)
        for _index, row in valid_df.iterrows():
            # Check if feature already exists for this time/company to avoid conflicts
            existing = (
                self.db.query(MLFeature)
                .filter(MLFeature.time == row["time"], MLFeature.company_id == company_id)
                .first()
            )

            p_l_val = self._to_decimal(row["p_l_ratio"])

            if not existing:
                feature = MLFeature(
                    time=row["time"],
                    company_id=company_id,
                    sma_20=self._to_decimal(row["sma_20"]),
                    sma_50=self._to_decimal(row["sma_50"]),
                    rsi_14=self._to_decimal(row["rsi_14"]),
                    volatility_20=self._to_decimal(row["volatility_20"]),
                    p_l_ratio=p_l_val,
                    target_next_day_change=self._to_decimal(row["target_next_day_change"]),
                )
                self.db.add(feature)
            else:
                # Update existing
                existing.sma_20 = self._to_decimal(row["sma_20"])
                existing.sma_50 = self._to_decimal(row["sma_50"])
                existing.rsi_14 = self._to_decimal(row["rsi_14"])
                existing.volatility_20 = self._to_decimal(row["volatility_20"])
                existing.p_l_ratio = p_l_val
                existing.target_next_day_change = self._to_decimal(row["target_next_day_change"])

        try:
            self.db.commit()
            logger.info(f"Features saved for company_id: {company_id}")
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Save features failed for company {company_id}: {exc}")
            raise DatabaseError("Failed to save ML features") from exc

    def _to_decimal(self, val: Any) -> Any:
        """Helper to convert to Decimal for SQLAlchemy persistence, handling pandas nulls."""
        if pd.isna(val):
            return None
        return Decimal(str(val))
