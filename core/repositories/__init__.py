"""Repositories: one class per aggregate (Company, Price, Fundamental,
Reliability). Replaces the previous monolithic ``DataService``.

Each repository takes a Session in __init__ and exposes the query/persist
operations for its aggregate. Routers and the engine instantiate the repos
they need — explicit is better than a god service.
"""

from .company_repository import CompanyRepository
from .fundamental_repository import FundamentalRepository
from .price_repository import PriceRepository
from .reliability_repository import ReliabilityRepository

__all__ = [
    "CompanyRepository",
    "FundamentalRepository",
    "PriceRepository",
    "ReliabilityRepository",
]
