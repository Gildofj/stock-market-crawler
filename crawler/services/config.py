import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database Configuration
    DATABASE_URL: str | None = None  # Highest priority (e.g., Supabase URL)

    DB_USER: str = "crawler_user"
    DB_PASSWORD: str = "crawler_pass"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "stock_market_crawler_data"

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

    # Crawler Settings
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
