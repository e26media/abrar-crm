from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Catering Management System"
    database_url: str = "postgresql+asyncpg://postgres:1234@localhost/catering_db"
    tax_percent: float = 0.0

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
