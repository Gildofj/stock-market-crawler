import uuid

from pydantic import BaseModel, ConfigDict, Field

from core.models.schemas import StockPriceSchema


class CrawlResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    name: str | None = None
    sector: str | None = None
    sub_sector: str | None = None
    segment: str | None = None
    logo_url: str | None = None
    website: str | None = None
    is_active: int = 1

    p_l: float | None = None
    p_vp: float | None = None
    dy: float | None = None
    roe: float | None = None
    roic: float | None = None
    ev_ebitda: float | None = None
    net_margin: float | None = None
    liquid_debt_ebitda: float | None = None
    cagr_revenue_5y: float | None = None
    cagr_profit_5y: float | None = None
    debt_to_equity: float | None = None
    market_cap: float | None = None
    eps: float | None = None
    shares_outstanding: float | None = None

    valuation_graham: float | None = None
    valuation_bazin: float | None = None
    quality_score: int | None = None

    prices: list[StockPriceSchema] = Field(default_factory=list)

    yahoo_info_indicators: dict[str, float] | None = None

    provenance: dict[str, str] = Field(default_factory=dict)

    primary_source_id: uuid.UUID | None = None
    contributing_sources: list[str] = Field(default_factory=list)

    def is_complete(self) -> bool:
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
        exclude = {"symbol", "prices", "yahoo_info_indicators"}
        for field, value in other.model_dump(exclude=exclude).items():
            current_val = getattr(self, field)

            if current_val is None and value is not None:
                setattr(self, field, value)

            elif field == "name" and current_val == self.symbol and value != self.symbol:
                setattr(self, field, value)

        if not self.prices and other.prices:
            self.prices = other.prices
