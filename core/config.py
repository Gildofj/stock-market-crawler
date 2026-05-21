import os
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"


class Settings(BaseSettings):
    DATABASE_URL: str | None = None

    DB_USER: str = "crawler_user"
    DB_PASSWORD: str = "crawler_pass"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "stock_market_crawler_data"

    # Kept small so parallel workers (e.g., GHA matrix chunks) stay within
    # Supabase's global client cap.
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 3

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

    REDIS_URL: str = _DEFAULT_REDIS_URL
    REDIS_HOST: str | None = None
    REDIS_PASSWORD: str | None = None
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def redis_url(self) -> str:
        url = self.REDIS_URL
        if url == _DEFAULT_REDIS_URL and self.REDIS_HOST and self.REDIS_PASSWORD:
            url = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        # Celery's redis backend refuses rediss:// without ssl_cert_reqs.
        if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}ssl_cert_reqs=CERT_REQUIRED"
        return url

    # Cloudflare R2 S3 credentials are derived from the API token:
    # access_key_id = first 32 hex chars of SHA-256(token); secret = token itself.
    # See https://developers.cloudflare.com/r2/api/tokens/.
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

    # Identity attributes exposed as OTel resource attrs and as serviceContext
    # on every JSON log line. SERVICE_VERSION should be the git SHA in CI.
    LOG_FORMAT: Literal["human", "gcp"] = "human"
    SERVICE_NAME: str = "stock-market-crawler"
    SERVICE_VERSION: str = "dev"
    DEPLOYMENT_ENV: str = "development"
    GCP_PROJECT_ID: str | None = None

    OTEL_ENABLED: bool = False
    OTEL_EXPORTER: Literal["console", "otlp", "gcp"] = "console"
    # Wrapped in ParentBased(TraceIdRatioBased). 0.05–0.10 in prod fits the
    # 2.5M-span/month Cloud Trace free tier.
    OTEL_SAMPLE_RATIO: float = 1.0
    # Redis instrumentation off by default because Celery broker polling would
    # otherwise dominate span volume.
    OTEL_INSTRUMENT_REDIS: bool = False

    @field_validator("GCP_PROJECT_ID", mode="before")
    @classmethod
    def _default_gcp_project(cls, value: str | None) -> str | None:
        if value:
            return value
        return os.getenv("GOOGLE_CLOUD_PROJECT")

    # When set, the crawler attaches an RFC 9110 `From:` header to outbound
    # requests — the standard signal for "robot operator email".
    CRAWLER_CONTACT_EMAIL: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def _coerce_empty_redis_url(cls, value: str | None) -> str:
        # GHA interpolates missing secrets as empty strings, which would
        # otherwise override the default and flip Celery's broker to amqp://.
        if value is None or (isinstance(value, str) and not value.strip()):
            return _DEFAULT_REDIS_URL
        return value


settings = Settings()
