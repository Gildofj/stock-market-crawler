import yfinance as yf
from loguru import logger

from ..models.schemas import CompanySchema, FundamentalSchema, StockPriceSchema
from ..services.data_service import DataService
from .base_spider import BaseSpider


class B3Spider(BaseSpider):
    def __init__(self, data_service: DataService):
        self.data_service = data_service

    def crawl_ticker(self, symbol: str):
        # B3 symbols in yfinance need .SA suffix
        yf_symbol = f"{symbol}.SA" if not symbol.endswith(".SA") else symbol
        logger.info(f"Crawling ticker: {yf_symbol}")

        ticker = yf.Ticker(yf_symbol)

        # Fast fail if no data (e.g. 404 Not Found or delisted)
        history = ticker.history(period="1y")

        # Inactivity Check Logic
        is_active = 1
        if history.empty:
            logger.warning(
                f"ACTION REQUIRED: {yf_symbol} is INACTIVE or DELISTED. Skipping collection."
            )
            return

        # Check for liquidity (last 5 trading days volume)
        recent_volume = history["Volume"].tail(5).sum()
        if recent_volume == 0:
            logger.warning(
                f"ACTION REQUIRED: {yf_symbol} has NO TRADING VOLUME. Marking as INACTIVE."
            )
            is_active = 0

        # 1. Get/Create Company with enriched data
        info = ticker.info

        # Priority: longName -> shortName -> symbol
        display_name = info.get("longName") or info.get("shortName")
        if not display_name or display_name.upper() == symbol.upper():
            # If yfinance fails to provide a real name, we use the symbol as fallback
            # but we'll hope Fundamentus or StatusInvest enriches it later.
            display_name = symbol.replace(".SA", "")

        company_schema = CompanySchema(
            symbol=symbol.replace(".SA", ""),
            name=display_name,
            sector=info.get("sector"),
            sub_sector=info.get("industry"),
            segment=info.get("quoteType"),
            is_active=is_active
        )
        company = self.data_service.get_or_create_company(company_schema)

        # 2. Get Historical Prices (Expanded to 1 year for better ML features)
        prices = []
        for index, row in history.iterrows():
            prices.append(
                StockPriceSchema(
                    time=index.to_pydatetime(),
                    open=row["Open"],
                    high=row["High"],
                    low=row["Low"],
                    close=row["Close"],
                    adj_close=row.get("Adj Close", row["Close"]),
                    volume=int(row["Volume"]),
                )
            )

        if prices:
            self.data_service.save_prices(company.id, prices)
            logger.info(f"Saved {len(prices)} price points for {symbol}")

        # 3. Get Fundamentals (Detailed Mapping)
        # Using forwardPE for P/L and priceToBook for P/VP
        fundamental_schema = FundamentalSchema(
            p_l=info.get("forwardPE") or info.get("trailingPE"),
            p_vp=info.get("priceToBook"),
            ev_ebitda=info.get("enterpriseToEbitda"),
            roe=info.get("returnOnEquity"),
            dy=info.get("dividendYield", 0) * 100 if info.get("dividendYield") else 0,
            net_margin=info.get("profitMargins"),
            liquid_debt_ebitda=info.get("debtToEbitda"),
            debt_to_equity=info.get("debtToEquity"),
            market_cap=info.get("marketCap"),
            eps=info.get("trailingEps")
        )
        self.data_service.save_fundamentals(company.id, fundamental_schema)
        logger.info(f"Saved enriched fundamentals for {symbol} (P/VP: {fundamental_schema.p_vp})")
