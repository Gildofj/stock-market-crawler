from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache

from api.deps import (
    CompanyRepoDep,
    FundamentalRepoDep,
    LakeServiceDep,
    ReliabilityRepoDep,
)
from api.limiter import DefaultRateLimit
from api.schemas import (
    CompanyRead,
    FundamentalRead,
    PortfolioSnapshotItem,
    PortfolioSnapshotResponse,
    ReliabilityResponse,
)
from core.models.models import LakeNews
from core.models.schemas import LakeNewsSchema

MAX_SYMBOLS_PER_REQUEST = 50

router = APIRouter(
    prefix="/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(DefaultRateLimit)],
)


def _parse_symbols(raw: str) -> list[str]:
    """Split, trim, upper-case and de-duplicate the CSV `symbols` query param.

    Preserves first-occurrence order so the response items match what the
    caller intuitively expects when echoing back the requested list.
    """
    seen: set[str] = set()
    parsed: list[str] = []
    for chunk in raw.split(","):
        symbol = chunk.strip().upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            parsed.append(symbol)
    return parsed


def _news_row_to_schema(row: LakeNews) -> LakeNewsSchema:
    return LakeNewsSchema(
        id=row.id,
        source=row.source,
        title=row.title,
        summary=row.summary,
        url=row.url,
        url_hash=row.url_hash,
        sentiment=row.sentiment,
        published_at=row.published_at,
        tickers=[t.ticker for t in row.tickers],
    )


@router.get(
    "/snapshot",
    response_model=PortfolioSnapshotResponse,
    summary="Aggregated snapshot for multiple tickers",
)
@cache(expire=120, namespace="portfolio:snapshot")
async def get_portfolio_snapshot(
    company_repo: CompanyRepoDep,
    fundamental_repo: FundamentalRepoDep,
    reliability_repo: ReliabilityRepoDep,
    lake: LakeServiceDep,
    symbols: str = Query(..., description="Comma-separated tickers (max 50). Case-insensitive."),
    news_per_symbol: int = Query(10, gt=0, le=20),
) -> PortfolioSnapshotResponse:
    """Returns company + fundamentals + reliability + top-N news per symbol.

    This endpoint aggregates data from multiple domains to provide a complete
    view for a user's portfolio or watchlist.

    Indicators included:
    - **P/L**: Price-to-Earnings ratio.
    - **DY**: Dividend Yield (%).
    - **ROE**: Return on Equity (%).
    - **ROIC**: Return on Invested Capital (%).
    - **EV/EBITDA**: Enterprise Value to EBITDA ratio.
    - **Reliability Score**: Composite score (0-100) based on profit consistency and debt.
    - **News**: Most recent market intelligence tagged with the symbol.

    Replaces the dashboard N×4 round-trip pattern with one request that
    issues 4 bulk SQL queries (independent of the symbol count).
    """
    parsed = _parse_symbols(symbols)
    if not parsed:
        raise HTTPException(status_code=422, detail="symbols query param cannot be empty")
    if len(parsed) > MAX_SYMBOLS_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=f"max {MAX_SYMBOLS_PER_REQUEST} symbols per request",
        )

    companies = await company_repo.get_many_by_symbols(parsed)
    if not companies:
        raise HTTPException(status_code=400, detail="no known symbols in request")

    company_ids = [c.id for c in companies]
    fundamentals_by_id = await fundamental_repo.get_latest_for_companies(company_ids)
    reliability_by_id = await reliability_repo.get_for_companies(company_ids)
    news_by_ticker = await lake.get_news_by_tickers(parsed, news_per_symbol)

    companies_by_symbol = {c.symbol: c for c in companies}

    items: list[PortfolioSnapshotItem] = []
    for symbol in parsed:
        company = companies_by_symbol.get(symbol)
        if company is None:
            items.append(PortfolioSnapshotItem(symbol=symbol, found=False))
            continue
        fundamental = fundamentals_by_id.get(company.id)
        reliability = reliability_by_id.get(company.id)
        news_rows = news_by_ticker.get(symbol, [])
        items.append(
            PortfolioSnapshotItem(
                symbol=symbol,
                found=True,
                company=CompanyRead.model_validate(company),
                fundamentals=FundamentalRead.model_validate(fundamental)
                if fundamental is not None
                else None,
                reliability=ReliabilityResponse.model_validate(reliability)
                if reliability is not None
                else None,
                news=[_news_row_to_schema(n) for n in news_rows],
            )
        )

    return PortfolioSnapshotResponse(
        items=items,
        requested=len(parsed),
        found=sum(1 for item in items if item.found),
        missing=[item.symbol for item in items if not item.found],
    )
