# backend/app/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import engine
from app.models.base import Base
from app.router import api_router

# ✅ Scheduler
from app.jobs.scheduler import run_startup_catchup, start_scheduler

import os

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

# ---------------------------
# Static folder (optional)
# ---------------------------

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------
# CORS (WSL + Local Dev 안전 설정)
# ---------------------------

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://haedori.ludo-lab.com",
    "http://haedori.ludo-lab.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# DB init (DEV only)
# ---------------------------

if os.getenv("ENV", "dev") == "dev":
    Base.metadata.create_all(bind=engine)

# ---------------------------
# Startup / Shutdown (Scheduler)
# ---------------------------

@app.on_event("startup")
async def on_startup():
    # ✅ 매일 00:00 KST 편지 생성, 06:00 KST 답장 알림 스케줄 시작
    start_scheduler()
    await run_startup_catchup()

@app.on_event("shutdown")
def on_shutdown():
    # 필요하면 여기에서 scheduler.shutdown() 같은 처리를 추가할 수 있음
    pass

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
