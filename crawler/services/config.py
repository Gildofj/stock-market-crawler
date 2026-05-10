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
        if self.DATABASE_URL:
            # If using Supabase/Cloud, ensure we handle sslmode if not provided
            if "supabase" in self.DATABASE_URL and "sslmode" not in self.DATABASE_URL:
                separator = "&" if "?" in self.DATABASE_URL else "?"
                return f"{self.DATABASE_URL}{separator}sslmode=require"
            return self.DATABASE_URL
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Crawler Settings
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
