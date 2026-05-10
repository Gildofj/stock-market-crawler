from pydantic import BaseModel, ConfigDict, Field

from .schemas import StockPriceSchema


class CrawlResult(BaseModel):
    """
    Unified container for data collected across multiple crawlers.

    This model serves as the internal 'contract' between different spiders
    and the CrawlerEngine. It facilitates the enrichment process by allowing
    multiple sources to contribute to the final dataset for a given symbol.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str = Field(..., description="Unique ticker symbol (e.g., AAPL, PETR4.SA)")
    name: str | None = Field(None, description="Full legal name of the company")
    sector: str | None = Field(None, description="Broad economic sector")
    sub_sector: str | None = Field(None, description="Industry sub-sector")
    segment: str | None = Field(None, description="Specific business segment")
    logo_url: str | None = Field(None, description="URL to the company's brand logo")
    website: str | None = Field(None, description="Company website URL")
    is_active: int = Field(1, description="Status of the stock (1 for active, 0 for inactive)")

    # Fundamental Indicators
    p_l: float | None = Field(None, description="Price to Earnings ratio")
    p_vp: float | None = Field(None, description="Price to Book Value ratio")
    dy: float | None = Field(None, description="Dividend Yield percentage")
    roe: float | None = Field(None, description="Return on Equity percentage")
    roic: float | None = Field(None, description="Return on Invested Capital percentage")
    ev_ebitda: float | None = Field(None, description="Enterprise Value / EBITDA ratio")
    net_margin: float | None = Field(None, description="Net Profit Margin percentage")
    liquid_debt_ebitda: float | None = Field(None, description="Net Debt / EBITDA ratio")
    cagr_revenue_5y: float | None = Field(None, description="5-Year Revenue CAGR percentage")
    cagr_profit_5y: float | None = Field(None, description="5-Year Profit CAGR percentage")
    debt_to_equity: float | None = Field(None, description="Total Debt / Total Equity ratio")
    market_cap: float | None = Field(None, description="Total market capitalization")
    eps: float | None = Field(None, description="Earnings Per Share")

    # Valuation & Scores
    valuation_graham: float | None = Field(None, description="Graham Fair Value Price")
    valuation_bazin: float | None = Field(None, description="Bazin Fair Value Price")
    quality_score: int | None = Field(None, description="Composite quality score (0-100)")

    # Historical Prices
    prices: list[StockPriceSchema] = Field(
        default_factory=list, description="List of historical price data points"
    )

    def __init__(self, **data):
        super().__init__(**data)

    def is_complete(self) -> bool:
        """
        Determines if the result has the minimum required set of indicators.

        A result is considered complete if it contains essential valuation
        and performance metrics used for basic analysis.
        """
        required_fields = [
            self.p_l,
            self.p_vp,
            self.dy,
            self.roe,
            self.market_cap,
            self.roic,
            self.liquid_debt_ebitda,
            self.cagr_revenue_5y,
        ]
        return all(field is not None for field in required_fields)

    def enrich(self, other: "CrawlResult") -> None:
        """
        Merges missing data from another CrawlResult instance into this one.

        Uses a 'fill-in-the-blanks' strategy: only fields that are currently None
        (or placeholder values like symbol for name) are updated.

        Args:
            other: The source CrawlResult to copy data from.
        """
        exclude = {"symbol", "prices"}
        for field, value in other.model_dump(exclude=exclude).items():
            current_val = getattr(self, field)

            # Fill if current is missing and other has value
            if current_val is None and value is not None:
                setattr(self, field, value)

            # Special case: replace name if it's just the symbol and other has a better name
            elif field == "name" and current_val == self.symbol and value != self.symbol:
                setattr(self, field, value)

        # Merge prices if current list is empty
        if not self.prices and other.prices:
            self.prices = other.prices
