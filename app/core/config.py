from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Pydantic v2 settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ✅ 모르는 env가 있어도 무시 (실무에서 편함)
    )

    # -------------------------
    # App
    # -------------------------
    APP_NAME: str = "Tarota Diary Backend"
    ENV: str = "development"
    DEBUG: bool = True

    # -------------------------
    # Server
    # -------------------------
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # -------------------------
    # Database
    # -------------------------
    DATABASE_URL: str = "sqlite:///./diary.db"

    # (옵션) 개별 값도 쓰고 싶으면 유지
    DB_DRIVER: str | None = None
    DB_HOST: str | None = None
    DB_PORT: int | None = None
    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None

    # -------------------------
    # Security / Auth
    # -------------------------
    SECRET_KEY: str = Field(default="change_this", min_length=8)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # -------------------------
    # Password hashing
    # -------------------------
    BCRYPT_ROUNDS: int = 12

    # -------------------------
    # LLM (Future)
    # -------------------------
    OPENAI_API_KEY: str | None = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.7

    # -------------------------
    # Notification (Future)
    # -------------------------
    DEFAULT_FORTUNE_HOUR: int = 8
    DEFAULT_DIARY_HOUR: int = 20
    TIMEZONE: str = "Asia/Seoul"


settings = Settings()
