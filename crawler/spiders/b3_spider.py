import yfinance as yf
from loguru import logger

from ..models.contract import CrawlResult
from ..models.schemas import StockPriceSchema
from .base_spider import BaseSpider


class B3Spider(BaseSpider):
    def crawl_ticker(self, symbol: str) -> CrawlResult:
        # B3 symbols in yfinance need .SA suffix
        yf_symbol = f"{symbol}.SA" if not symbol.endswith(".SA") else symbol
        logger.info(f"Crawling ticker: {yf_symbol}")

        result = CrawlResult(symbol=symbol)
        ticker = yf.Ticker(yf_symbol)

        # Fast fail if no data (e.g. 404 Not Found or delisted)
        history = ticker.history(period="1y")

        if history.empty:
            logger.warning(
                f"ACTION REQUIRED: {yf_symbol} is INACTIVE or DELISTED. Skipping collection."
            )
            return result

        # Check for liquidity (last 5 trading days volume)
        recent_volume = history["Volume"].tail(5).sum()
        if recent_volume == 0:
            logger.warning(
                f"ACTION REQUIRED: {yf_symbol} has NO TRADING VOLUME. Marking as INACTIVE."
            )
            result.is_active = 0

        # 1. Company Metadata
        info = ticker.info

        # Priority: longName -> shortName -> symbol
        display_name = info.get("longName") or info.get("shortName")
        if not display_name or display_name.upper() == symbol.upper():
            display_name = symbol.replace(".SA", "")

        result.name = display_name
        result.sector = info.get("sector")
        result.sub_sector = info.get("industry")
        result.segment = info.get("quoteType")

        # 2. Historical Prices
        for index, row in history.iterrows():
            result.prices.append(
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

        # 3. Fundamentals
        result.p_l = info.get("forwardPE") or info.get("trailingPE")
        result.p_vp = info.get("priceToBook")
        result.ev_ebitda = info.get("enterpriseToEbitda")
        result.roe = info.get("returnOnEquity")
        result.dy = info.get("dividendYield", 0) * 100 if info.get("dividendYield") else 0
        result.net_margin = info.get("profitMargins")
        result.liquid_debt_ebitda = info.get("debtToEbitda")
        result.debt_to_equity = info.get("debtToEquity")
        result.market_cap = info.get("marketCap")
        result.eps = info.get("trailingEps")

        return result
