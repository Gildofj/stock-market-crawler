from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database Configuration
    DB_USER: str = "crawler_user"
    DB_PASSWORD: str = "crawler_pass"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "b3_data"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Crawler Settings
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
