import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile

from api.deps import DBDep, PremiumUserDep
from api.limiter import DefaultRateLimit
from crawler.models.schemas import (
    FundamentalSchema,
    PortfolioAssetSchema,
    PortfolioCreateSchema,
    PortfolioSchema,
    StockPriceSchema,
)
from crawler.services.data_service import DataService
from crawler.services.portfolio_service import (
    PortfolioParseError,
    PortfolioService,
)
from crawler.services.storage_service import get_storage

router = APIRouter(
    prefix="/carteira",
    tags=["Portfolio"],
    dependencies=[Depends(DefaultRateLimit)],
)


def _portfolio_to_schema(portfolio) -> PortfolioSchema:
    return PortfolioSchema(
        id=portfolio.id,
        name=portfolio.name,
        source_filename=portfolio.source_filename,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        assets=[PortfolioAssetSchema.model_validate(a) for a in portfolio.assets],
    )


def _portfolio_r2_key(user_id: uuid.UUID, filename: str) -> str:
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    return f"{user_id}/{uuid.uuid4()}-{safe_name}"


@router.post(
    "",
    response_model=PortfolioSchema,
    status_code=201,
    summary="Create a portfolio (JSON body or spreadsheet upload)",
)
async def create_portfolio(
    db: DBDep,
    user: PremiumUserDep,
    file: Annotated[UploadFile | None, File()] = None,
    name: Annotated[str | None, Form()] = None,
    payload: Annotated[PortfolioCreateSchema | None, Body()] = None,
):
    service = PortfolioService(db)

    if file is not None:
        content = await file.read()
        filename = file.filename or "carteira.xlsx"
        content_type = file.content_type or "application/octet-stream"
        try:
            assets = PortfolioService.parse_spreadsheet(content, filename)
        except PortfolioParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Mirror the original spreadsheet into the private R2 bucket so the user
        # can re-download it later and we have an evidence trail for parsing.
        # Falls back gracefully when R2 is not configured.
        storage = get_storage()
        r2_key = storage.upload_portfolio_file(
            _portfolio_r2_key(user.id, filename), content, content_type
        )

        portfolio_name = name or filename[:100]
        portfolio = service.create_portfolio(
            user.id,
            portfolio_name,
            assets,
            source_r2_key=r2_key,
            source_filename=filename,
            source_content_type=content_type,
        )
    elif payload is not None:
        portfolio = service.create_portfolio(user.id, payload.name, payload.assets)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a spreadsheet (file) or a JSON body.",
        )

    return _portfolio_to_schema(portfolio)


@router.get(
    "/{portfolio_id}/source-url",
    summary="Presigned URL to download the original spreadsheet",
)
async def get_portfolio_source_url(
    portfolio_id: uuid.UUID,
    db: DBDep,
    user: PremiumUserDep,
):
    service = PortfolioService(db)
    portfolio = service.get_portfolio(portfolio_id, user.id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if not portfolio.source_r2_key:
        raise HTTPException(
            status_code=404,
            detail="This portfolio was not created from a spreadsheet upload.",
        )
    url = get_storage().presigned_portfolio_url(portfolio.source_r2_key)
    if not url:
        raise HTTPException(
            status_code=503,
            detail="Object storage is not available right now.",
        )
    return {
        "url": url,
        "filename": portfolio.source_filename,
        "content_type": portfolio.source_content_type,
    }


@router.get("", response_model=list[PortfolioSchema], summary="List user portfolios")
async def list_portfolios(db: DBDep, user: PremiumUserDep):
    service = PortfolioService(db)
    return [_portfolio_to_schema(p) for p in service.list_portfolios(user.id)]


@router.get(
    "/{portfolio_id}",
    summary="Get a portfolio with enriched market data",
)
async def get_portfolio(
    portfolio_id: uuid.UUID,
    db: DBDep,
    user: PremiumUserDep,
):
    service = PortfolioService(db)
    portfolio = service.get_portfolio(portfolio_id, user.id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    data_service = DataService(db)
    enriched_assets = []
    for asset in portfolio.assets:
        company = data_service.get_company_by_symbol(asset.ticker)
        latest_price = None
        latest_fundamentals = None
        if company:
            prices = data_service.get_price_history(company.id, limit=1)
            if prices:
                latest_price = StockPriceSchema.model_validate(prices[0])
            fundamentals = data_service.get_latest_fundamentals(company.id)
            if fundamentals:
                latest_fundamentals = FundamentalSchema.model_validate(fundamentals)

        enriched_assets.append(
            {
                "asset": PortfolioAssetSchema.model_validate(asset),
                "latest_price": latest_price,
                "fundamentals": latest_fundamentals,
            }
        )

    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "created_at": portfolio.created_at,
        "updated_at": portfolio.updated_at,
        "assets": enriched_assets,
    }


@router.delete("/{portfolio_id}", status_code=204, summary="Delete a portfolio")
async def delete_portfolio(
    portfolio_id: uuid.UUID,
    db: DBDep,
    user: PremiumUserDep,
):
    service = PortfolioService(db)
    deleted = service.delete_portfolio(portfolio_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return None
