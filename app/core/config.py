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

    # LLM 연결 설정
    LLM_BASE_URL: str = "http://open-webui:8080"
    LLM_API_KEY: Optional[str] = Field(
        default=None,
        description="Open WebUI API key (Bearer). Raw Ollama only setups can leave this empty.",
    )
    LLM_MODEL: str = "dori-text-v6"
    QUESTION_LLM_MODEL: str = "dori-diary-question"
    SUMMARY_LLM_MODEL: str = "dori-summary"
    FORTUNE_LLM_MODEL: str = "saju-v0"
    SAJU_LLM_MODEL: str = "saju-reading-v0"
    LLM_PROVIDER: str = "auto"
    LLM_FALLBACK_BASE_URLS: str = ""

    LLM_TIMEOUT_SEC: int = 180


settings = Settings()