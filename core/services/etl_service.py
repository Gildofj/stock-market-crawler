import uuid
from decimal import Decimal
from typing import Any

import pandas as pd
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from core.models.models import Fundamental, MLFeature, StockPrice


class ETLService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_features(self, company_id: uuid.UUID):
        logger.info(f"Generating ML features for company_id: {company_id}")

        stmt_prices = (
            select(StockPrice).filter(StockPrice.company_id == company_id).order_by(StockPrice.time)
        )
        result_prices = await self.db.execute(stmt_prices)
        prices = result_prices.scalars().all()

        if not prices:
            return

        stmt_fundamentals = (
            select(Fundamental)
            .filter(Fundamental.company_id == company_id)
            .order_by(Fundamental.collected_at.desc())
            .limit(1)
        )
        result_fundamentals = await self.db.execute(stmt_fundamentals)
        latest_fundamental = result_fundamentals.scalars().first()

        eps: float | None = None
        if latest_fundamental and latest_fundamental.eps is not None:
            eps = float(latest_fundamental.eps)

        df = pd.DataFrame(
            [{"time": p.time, "close": float(p.close), "volume": p.volume} for p in prices]
        )

        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["sma_50"] = df["close"].rolling(window=50).mean()

        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi_14"] = 100 - (100 / (1 + rs))

        df["volatility_20"] = df["close"].rolling(window=20).std()

        if eps and eps > 0:
            df["p_l_ratio"] = df["close"] / eps
        else:
            df["p_l_ratio"] = None

        df["target_next_day_change"] = df["close"].shift(-1) / df["close"] - 1

        essential_cols = ["sma_20", "sma_50", "rsi_14", "volatility_20", "target_next_day_change"]

        valid_df = df.dropna(subset=essential_cols)
        for _index, row in valid_df.iterrows():
            stmt_existing = select(MLFeature).filter(
                MLFeature.time == row["time"], MLFeature.company_id == company_id
            )
            result_existing = await self.db.execute(stmt_existing)
            existing = result_existing.scalars().first()

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
                existing.sma_20 = self._to_decimal(row["sma_20"])
                existing.sma_50 = self._to_decimal(row["sma_50"])
                existing.rsi_14 = self._to_decimal(row["rsi_14"])
                existing.volatility_20 = self._to_decimal(row["volatility_20"])
                existing.p_l_ratio = p_l_val
                existing.target_next_day_change = self._to_decimal(row["target_next_day_change"])

        try:
            await self.db.commit()
            logger.info(f"Features saved for company_id: {company_id}")
        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.error(f"Save features failed for company {company_id}: {exc}")
            raise DatabaseError("Failed to save ML features") from exc

    def _to_decimal(self, val: Any) -> Any:
        if pd.isna(val):
            return None
        return Decimal(str(val))
