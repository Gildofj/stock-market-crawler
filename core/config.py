import os
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str | None = None

    DB_USER: str = "crawler_user"
    DB_PASSWORD: str = "crawler_pass"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "stock_market_crawler_data"

    # Sized for Supabase free tier behind Supavisor transaction pooler (port 6543):
    # the pooler multiplexes a small app-side pool onto fewer real Postgres
    # connections, so 5+10=15 per service × 2 services = 30 total stays well
    # under the free-tier ceiling. Aligned with cloud_tasks.tf max_concurrent_dispatches.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    # Hard cap on any single query at the Postgres level (ms). Stops a runaway
    # query from holding a pool slot forever; pairs with pool_timeout=30s.
    DB_STATEMENT_TIMEOUT_MS: int = 30_000

    @property
    def database_url(self) -> str:
        current_url = os.getenv("DATABASE_URL") or self.DATABASE_URL

        if current_url:
            if current_url.startswith("postgres://"):
                current_url = current_url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif current_url.startswith("postgresql://") and "+asyncpg" not in current_url:
                current_url = current_url.replace("postgresql://", "postgresql+asyncpg://", 1)

            if "sslmode=" in current_url:
                current_url = current_url.replace("sslmode=", "ssl=")

            if "supabase" in current_url and "ssl=" not in current_url:
                separator = "&" if "?" in current_url else "?"
                return f"{current_url}{separator}ssl=require"
            return current_url

        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    R2_ACCOUNT_ID: str | None = None
    R2_API_TOKEN: str | None = None
    R2_BUCKET_RI_DOCS: str = "ri-docs"
    R2_BUCKET_PORTFOLIOS: str = "portfolios"
    R2_RI_PUBLIC_BASE_URL: str | None = None
    R2_PRESIGN_TTL_SECONDS: int = 900

    @property
    def r2_credentials(self) -> tuple[str, str] | None:
        if self.R2_API_TOKEN:
            import hashlib

            digest = hashlib.sha256(self.R2_API_TOKEN.encode("utf-8")).hexdigest()
            return digest[:32], self.R2_API_TOKEN
        return None

    @property
    def r2_enabled(self) -> bool:
        return bool(self.R2_ACCOUNT_ID and self.r2_credentials)

    LOG_LEVEL: str = "INFO"

    LOG_FORMAT: Literal["human", "gcp"] = "human"
    SERVICE_NAME: str = "stock-market-crawler"
    SERVICE_VERSION: str = "dev"
    DEPLOYMENT_ENV: str = "development"
    GCP_PROJECT_ID: str | None = None

    OTEL_ENABLED: bool = False
    OTEL_EXPORTER: Literal["console", "otlp", "gcp"] = "console"
    OTEL_SAMPLE_RATIO: float = 1.0

    @field_validator("GCP_PROJECT_ID", mode="before")
    @classmethod
    def _default_gcp_project(cls, value: str | None) -> str | None:
        if value:
            return value
        return os.getenv("GOOGLE_CLOUD_PROJECT")

    @field_validator(
        "R2_ACCOUNT_ID",
        "R2_API_TOKEN",
        "R2_RI_PUBLIC_BASE_URL",
        "CRAWLER_HTTP_PROXY",
        "CRAWLER_HTTPS_PROXY",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        # Secret Manager bootstrap writes a single space for unset optional
        # secrets (terraform/secrets.tf); normalise back to None so truthy
        # checks behave as expected.
        # Also strip surrounding whitespace — `gcloud secrets versions add`
        # via stdin often appends \r\n, which httpx rejects as an illegal
        # header value when the secret is used in an Authorization header.
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None

    CRAWLER_CONTACT_EMAIL: str = ""

    CRAWLER_HTTP_PROXY: str | None = None
    CRAWLER_HTTPS_PROXY: str | None = None

    # Hostnames that bypass the residential proxy. Brazilian gov/exchange
    # endpoints have no anti-bot defense and routing them through webshare
    # only adds failure modes (e.g. 407 when the secret rotates).
    CRAWLER_PROXY_BYPASS_DOMAINS: str = (
        "dados.cvm.gov.br,arquivos.b3.com.br,api.bcb.gov.br,www3.bcb.gov.br,"
        "sistemaswebb3-listados.b3.com.br,www.b3.com.br,"
        "query1.finance.yahoo.com,query2.finance.yahoo.com"
    )

    @property
    def proxy_bypass_set(self) -> frozenset[str]:
        return frozenset(
            host.strip().lower()
            for host in self.CRAWLER_PROXY_BYPASS_DOMAINS.split(",")
            if host.strip()
        )

    # Tier 2 stealth (nodriver headless browser) requires Chromium installed
    # locally. The base Docker image is slim and has no browser — Tier 2 must
    # stay off there. The dedicated Dockerfile.stealth opts in by exporting
    # ENABLE_TIER2_STEALTH=true.
    ENABLE_TIER2_STEALTH: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
