from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db as get_crawler_db
from core.repositories import (
    CompanyRepository,
    FundamentalRepository,
    PriceRepository,
    ReliabilityRepository,
)
from core.services.lake_service import LakeService

DBDep = Annotated[AsyncSession, Depends(get_crawler_db)]


def get_company_repo(db: DBDep) -> CompanyRepository:
    return CompanyRepository(db)


def get_fundamental_repo(db: DBDep) -> FundamentalRepository:
    return FundamentalRepository(db)


def get_price_repo(db: DBDep) -> PriceRepository:
    return PriceRepository(db)


def get_reliability_repo(db: DBDep) -> ReliabilityRepository:
    return ReliabilityRepository(db)


def get_lake_service(db: DBDep) -> LakeService:
    return LakeService(db)


CompanyRepoDep = Annotated[CompanyRepository, Depends(get_company_repo)]
FundamentalRepoDep = Annotated[FundamentalRepository, Depends(get_fundamental_repo)]
PriceRepoDep = Annotated[PriceRepository, Depends(get_price_repo)]
ReliabilityRepoDep = Annotated[ReliabilityRepository, Depends(get_reliability_repo)]
LakeServiceDep = Annotated[LakeService, Depends(get_lake_service)]
