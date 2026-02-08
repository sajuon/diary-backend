from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


BASE_DIR = Path(__file__).resolve().parents[2]  # .../diary-backend/app/core -> .../diary-backend
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),          # ✅ 절대경로로 .env 지정
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Tarota Diary Backend"
    ENV: str = "development"
    DEBUG: bool = True

    # ✅ .env 없으면 바로 에러 나게 (sqlite로 떨어지지 않게)
    DATABASE_URL: str = Field(..., description="Database connection URL")

    SECRET_KEY: str = Field(..., min_length=8)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


settings = Settings()
