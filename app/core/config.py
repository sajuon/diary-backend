# /home/dori/diary-backend/app/core/config.py
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

    APP_NAME: str = "Haedori Backend"
    ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = Field(..., description="Database connection URL")

    SECRET_KEY: str = Field(..., min_length=8)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # refresh token 설정
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_COOKIE_NAME: str = "haedori_refresh_token"
    REFRESH_COOKIE_SECURE: bool = False
    REFRESH_COOKIE_SAMESITE: str = "lax"
    REFRESH_COOKIE_DOMAIN: Optional[str] = None

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

    # 편지 배치 스케줄 설정 (KST 기준)
    # LETTER_GENERATE_*: 전날 일기를 모아 LLM으로 편지를 생성하는 시각
    # LETTER_PUSH_*: 생성된 편지에 대해 푸시 알림을 발송하는 시각
    LETTER_GENERATE_HOUR: int = Field(default=0, ge=0, le=23)
    LETTER_GENERATE_MINUTE: int = Field(default=0, ge=0, le=59)
    LETTER_PUSH_HOUR: int = Field(default=6, ge=0, le=23)
    LETTER_PUSH_MINUTE: int = Field(default=0, ge=0, le=59)

    # 실험용: True면 "오늘" 일기를 대상으로 편지 생성 (운영은 반드시 False)
    LETTER_TARGET_TODAY: bool = False

    # Google Play 심사(리뷰어) 전용 우회 로그인 설정
    REVIEWER_TEST_EMAIL: Optional[str] = None
    REVIEWER_TEST_PASSWORD: Optional[str] = None
    REVIEWER_TEST_USER_ID: Optional[int] = None


settings = Settings()