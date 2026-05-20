import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"


class Settings(BaseSettings):
    # Database Configuration
    DATABASE_URL: str | None = None  # Highest priority (e.g., Supabase URL)

    DB_USER: str = "crawler_user"
    DB_PASSWORD: str = "crawler_pass"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "stock_market_crawler_data"

    # Connection pool sizing — kept small on purpose so multiple parallel workers
    # (e.g., GHA matrix chunks) stay within Supabase's global client cap.
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 3

    @property
    def database_url(self) -> str:
        # Re-fetch from env to catch any runtime patches (like IPv4 hostaddr)
        current_url = os.getenv("DATABASE_URL") or self.DATABASE_URL

        if current_url:
            # Ensure scheme is postgresql+asyncpg for SQLAlchemy Async
            if current_url.startswith("postgres://"):
                current_url = current_url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif current_url.startswith("postgresql://") and "+asyncpg" not in current_url:
                current_url = current_url.replace("postgresql://", "postgresql+asyncpg://", 1)

            # If using Supabase/Cloud, ensure we handle sslmode if not provided
            if "supabase" in current_url and "sslmode" not in current_url:
                separator = "&" if "?" in current_url else "?"
                return f"{current_url}{separator}sslmode=require"
            return current_url

        # Fallback to local config with asyncpg
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis Configuration
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
        # Celery's redis backend refuses to start on a rediss:// URL unless
        # ssl_cert_reqs is present. Managed providers (like Upstash) ship
        # valid public CA certs, so CERT_REQUIRED is the right default.
        if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}ssl_cert_reqs=CERT_REQUIRED"
        return url

    # Cloudflare R2 (S3-compatible) Object Storage.
    #
    # Cloudflare's current dashboard returns a single Bearer Token for R2.
    # The S3 Access Key ID is derived from it as the first 32 hex chars of
    # SHA-256(token), and the token itself is used as the S3 Secret Access Key.
    # This is the standard R2 contract — see
    # https://developers.cloudflare.com/r2/api/tokens/.
    R2_ACCOUNT_ID: str | None = None
    R2_API_TOKEN: str | None = None
    R2_BUCKET_RI_DOCS: str = "ri-docs"
    R2_BUCKET_PORTFOLIOS: str = "portfolios"
    # Public base URL for the RI bucket (e.g. https://pub-xxx.r2.dev or
    # a custom CNAME). Empty disables public-URL generation.
    R2_RI_PUBLIC_BASE_URL: str | None = None
    R2_PRESIGN_TTL_SECONDS: int = 900

    @property
    def r2_credentials(self) -> tuple[str, str] | None:
        """Returns the (access_key_id, secret_access_key) pair for boto3.

        Derives the S3 credentials from the Cloudflare R2 API token via SHA-256.
        """
        if self.R2_API_TOKEN:
            import hashlib

            digest = hashlib.sha256(self.R2_API_TOKEN.encode("utf-8")).hexdigest()
            return digest[:32], self.R2_API_TOKEN
        return None

    @property
    def r2_enabled(self) -> bool:
        return bool(self.R2_ACCOUNT_ID and self.r2_credentials)

    # Crawler Settings
    LOG_LEVEL: str = "INFO"

    # Optional operator contact email. When set, the crawler attaches an RFC 9110
    # `From:` header to every outbound request — the standard signal for "robot
    # operator email". It is the recommended way for a commercial operator to
    # identify themselves without disabling the realistic User-Agent rotation
    # used to bypass anti-bot challenges. Empty means no header is sent.
    CRAWLER_CONTACT_EMAIL: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def _coerce_empty_redis_url(cls, value: str | None) -> str:
        # GitHub Actions interpolates missing secrets as empty strings, which
        # would otherwise override the default and silently flip Celery's broker
        # back to amqp://.
        if value is None or (isinstance(value, str) and not value.strip()):
            return _DEFAULT_REDIS_URL
        return value


settings = Settings()
