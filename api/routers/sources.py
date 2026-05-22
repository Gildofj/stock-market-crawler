from fastapi import APIRouter, Depends
from fastapi_cache.decorator import cache
from pydantic import BaseModel, ConfigDict

from api.limiter import DefaultRateLimit
from core.services.source_registry import get_source_registry


class PublicDataSourceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    display_name: str
    homepage_url: str
    tos_url: str | None = None
    license_label: str | None = None
    risk_tier: str


router = APIRouter(
    prefix="/sources",
    tags=["Transparency"],
    dependencies=[Depends(DefaultRateLimit)],
)


@router.get(
    "",
    response_model=list[PublicDataSourceSchema],
    summary="List of enabled data sources powering this deployment",
)
@cache(expire=1800, namespace="sources:list")
async def list_sources() -> list[PublicDataSourceSchema]:
    registry = get_source_registry()
    return [
        PublicDataSourceSchema(
            slug=record.slug,
            display_name=record.display_name,
            homepage_url=record.homepage_url,
            tos_url=record.tos_url,
            license_label=record.license_label,
            risk_tier=record.risk_tier,
        )
        for record in await registry.all_enabled()
    ]
