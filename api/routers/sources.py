"""Public transparency endpoint listing the data sources powering the deployment.

Intentionally unauthenticated so the rendaraq ``/about/data-sources`` page,
auditors, and source publishers themselves can verify exactly which feeds
this deployment is collecting from. The endpoint reflects the
``data_sources`` table — an operator who disables a row via SQL sees it
drop out of this response within ~30 seconds (registry cache TTL).
"""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from core.services.source_registry import get_source_registry


class PublicDataSourceSchema(BaseModel):
    """Public-safe projection of a ``data_sources`` row.

    Omits operational fields (``contact_email``, ``notes``,
    ``last_reviewed_at``) on purpose — they belong to the operator's
    internal workflow, not the public transparency surface.
    """

    model_config = ConfigDict(from_attributes=True)

    slug: str = Field(..., description="Stable source identifier used in attribution.")
    display_name: str = Field(..., description="Human-readable name shown to users.")
    homepage_url: str = Field(..., description="Source homepage URL.")
    tos_url: str | None = Field(default=None, description="Terms of Service URL, if known.")
    license_label: str | None = Field(
        default=None,
        description=(
            "Informal legal posture "
            "(public-domain, rss-fair-use, tos-restricted, unknown)."
        ),
    )
    risk_tier: str = Field(
        ...,
        description="Operator's informal risk assessment (low | medium | high).",
    )


router = APIRouter(prefix="/sources", tags=["Transparency"])


@router.get(
    "",
    response_model=list[PublicDataSourceSchema],
    summary="List of enabled data sources powering this deployment",
)
async def list_sources() -> list[PublicDataSourceSchema]:
    registry = get_source_registry()
    # ``all_enabled`` returns a sorted snapshot already.
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
