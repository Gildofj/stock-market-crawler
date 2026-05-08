import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from ..models.models import StockPrice, MLFeature
from loguru import logger

class ETLService:
    def __init__(self, db: Session):
        self.db = db

    def generate_features(self, company_id: int):
        logger.info(f"Generating ML features for company_id: {company_id}")
        
        # 1. Load data into Pandas
        prices = self.db.query(StockPrice).filter(StockPrice.company_id == company_id).order_by(StockPrice.time).all()
        if not prices:
            return

        df = pd.DataFrame([{
            "time": p.time,
            "close": float(p.close),
            "volume": p.volume
        } for p in prices])

        # 2. Calculate Indicators
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1  + rs))

        df['volatility_20'] = df['close'].rolling(window=20).std()

        # Target: Percentage change of next day
        df['target_next_day_change'] = df['close'].shift(-1) / df['close'] - 1

        # 3. Save to DB
        for index, row in df.dropna().iterrows():
            feature = MLFeature(
                time=row['time'],
                company_id=company_id,
                sma_20=row['sma_20'],
                sma_50=row['sma_50'],
                rsi_14=row['rsi_14'],
                volatility_20=row['volatility_20'],
                target_next_day_change=row['target_next_day_change']
            )
            self.db.merge(feature)
        
        self.db.commit()
        logger.info(f"Features saved for company_id: {company_id}")
