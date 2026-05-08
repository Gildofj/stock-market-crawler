import yfinance as yf
from datetime import datetime, timedelta
from ..models.schemas import CompanySchema, StockPriceSchema, FundamentalSchema
from .data_service import DataService
from loguru import logger

class B3Spider:
    def __init__(self, data_service: DataService):
        self.data_service = data_service

    def crawl_ticker(self, symbol: str):
        # B3 symbols in yfinance need .SA suffix
        yf_symbol = f"{symbol}.SA" if not symbol.endswith(".SA") else symbol
        logger.info(f"Crawling ticker: {yf_symbol}")
        
        ticker = yf.Ticker(yf_symbol)
        
        # 1. Get/Create Company
        info = ticker.info
        company_schema = CompanySchema(
            symbol=symbol.replace(".SA", ""),
            name=info.get("longName"),
            sector=info.get("sector"),
            sub_sector=info.get("industry"),
            segment=info.get("quoteType")
        )
        company = self.data_service.get_or_create_company(company_schema)

        # 2. Get Historical Prices (last 30 days for example)
        history = ticker.history(period="1mo")
        prices = []
        for index, row in history.iterrows():
            prices.append(StockPriceSchema(
                time=index.to_pydatetime(),
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                adj_close=row.get("Adj Close", row["Close"]),
                volume=int(row["Volume"])
            ))
        
        if prices:
            self.data_service.save_prices(company.id, prices)
            logger.info(f"Saved {len(prices)} price points for {symbol}")

        # 3. Get Fundamentals
        fundamental_schema = FundamentalSchema(
            p_l=info.get("forwardPE"),
            p_vp=info.get("priceToBook"),
            ev_ebitda=info.get("enterpriseToEbitda"),
            roe=info.get("returnOnEquity"),
            dy=info.get("dividendYield", 0) * 100 if info.get("dividendYield") else None
            # Add more mapping as needed
        )
        self.data_service.save_fundamentals(company.id, fundamental_schema)
        logger.info(f"Saved fundamentals for {symbol}")
