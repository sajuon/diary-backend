from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import engine
from app.models.base import Base
from app.router import api_router

# ---------------------------
# App initialization
# ---------------------------

setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# static 폴더 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------
# CORS
# ---------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 배포 시 프론트 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# DB init (DEV only)
# ---------------------------
# ⚠️ 개발 단계에서만 사용
# ⚠️ 운영 환경에서는 Alembic 마이그레이션 사용 권장
Base.metadata.create_all(bind=engine)

# ---------------------------
# Router
# ---------------------------

app.include_router(api_router)

# ---------------------------
# Root
# ---------------------------

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "status": "running",
    }
