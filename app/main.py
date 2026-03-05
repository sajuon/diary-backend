from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import engine
from app.models.base import Base
from app.router import api_router

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
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,   # ❗ "*" 대신 명확히 지정
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