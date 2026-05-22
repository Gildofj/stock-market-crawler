import pytest

from core.models.schemas import CompanySchema


@pytest.mark.asyncio
async def test_get_or_create_preserves_existing_metadata_when_payload_is_none(company_repo):
    seeded = await company_repo.get_or_create(
        CompanySchema(
            symbol="PETR4",
            name="Petrobras",
            sector="Energy",
            sub_sector="Oil & Gas",
            segment="Integrated",
            website="https://petrobras.com.br",
            logo_url="https://logo.clearbit.com/petrobras.com.br",
        )
    )
    assert seeded.sector == "Energy"

    await company_repo.get_or_create(
        CompanySchema(
            symbol="PETR4",
            name=None,
            sector=None,
            sub_sector=None,
            segment=None,
            website=None,
            logo_url=None,
        )
    )

    refreshed = await company_repo.get_by_symbol("PETR4")
    assert refreshed.name == "Petrobras"
    assert refreshed.sector == "Energy"
    assert refreshed.sub_sector == "Oil & Gas"
    assert refreshed.segment == "Integrated"
    assert refreshed.website == "https://petrobras.com.br"
    assert refreshed.logo_url == "https://logo.clearbit.com/petrobras.com.br"


@pytest.mark.asyncio
async def test_get_or_create_still_updates_with_non_none_value(company_repo):
    await company_repo.get_or_create(CompanySchema(symbol="VALE3", name="Vale", sector="Materials"))

    await company_repo.get_or_create(
        CompanySchema(symbol="VALE3", name="Vale S.A.", sector="Basic Materials")
    )

    refreshed = await company_repo.get_by_symbol("VALE3")
    assert refreshed.name == "Vale S.A."
    assert refreshed.sector == "Basic Materials"


@pytest.mark.asyncio
async def test_get_or_create_fills_previously_null_field(company_repo):
    await company_repo.get_or_create(CompanySchema(symbol="ITUB4", name="Itaú"))

    await company_repo.get_or_create(
        CompanySchema(symbol="ITUB4", name="Itaú", sector="Financial Services")
    )

    refreshed = await company_repo.get_by_symbol("ITUB4")
    assert refreshed.sector == "Financial Services"
