from fastapi import APIRouter

from app.api import (
    health,
    auth,
    users,
    profile,
    fortunes,
    diary,
    letters,
    settings as settings_api,
)

api_router = APIRouter()

# 라우터 등록
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(profile.router)
api_router.include_router(fortunes.router)
api_router.include_router(diary.router)
api_router.include_router(letters.router)
api_router.include_router(settings_api.router)
