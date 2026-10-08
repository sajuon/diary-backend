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
    shop,
    dashboard,
    saju,
    web_push,
    reports,
    pearls,
    room,
    haedori,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(profile.router)
api_router.include_router(fortunes.router)
api_router.include_router(diary.router)
api_router.include_router(letters.router)
api_router.include_router(settings_api.router)
api_router.include_router(shop.router)
api_router.include_router(dashboard.router)
api_router.include_router(saju.router)
api_router.include_router(web_push.router)
api_router.include_router(reports.router)
api_router.include_router(pearls.router)
api_router.include_router(room.router)
api_router.include_router(haedori.router)