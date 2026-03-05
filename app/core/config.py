# app/core/config.py

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Tarota Diary Backend"
    ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = Field(..., description="Database connection URL")

    SECRET_KEY: str = Field(..., min_length=8)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    KAKAO_CLIENT_ID: Optional[str] = None
    KAKAO_CLIENT_SECRET: Optional[str] = None
    KAKAO_REDIRECT_URI: Optional[str] = None
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # ✅ Open WebUI(LLM) 연결 설정
    LLM_BASE_URL: str = "http://125.134.126.240:3615"
    LLM_API_KEY: str = Field(..., description="Open WebUI API key (Bearer)")
    LLM_MODEL: str = "dori-text-v6"

    # 49초 걸린 걸 봤으니 30초는 너무 짧음
    LLM_TIMEOUT_SEC: int = 180

settings = Settings()