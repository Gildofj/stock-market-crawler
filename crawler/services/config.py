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
            # If using Supabase/Cloud, ensure we handle sslmode if not provided
            if "supabase" in current_url and "sslmode" not in current_url:
                separator = "&" if "?" in current_url else "?"
                return f"{current_url}{separator}sslmode=require"
            return current_url
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis Configuration
    REDIS_URL: str = _DEFAULT_REDIS_URL

    # Crawler Settings
    LOG_LEVEL: str = "INFO"

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
