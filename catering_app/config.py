from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import os

class Settings(BaseSettings):
    app_name: str = "Catering Management System"
    database_url: str = "postgresql+asyncpg://postgres:1234@localhost/catering_db"
    tax_percent: float = 0.0
    
    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str) -> str:
        if not v:
            return v
        # Render/Heroku often provide postgres://, but SQLAlchemy 1.4+ requires postgresql://
        # Also we need to inject +asyncpg for our async driver
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
