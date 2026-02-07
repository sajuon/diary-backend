from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.settings import NotificationSettings
from app.schemas.settings import NotificationSettingsResponse, NotificationSettingsUpdateRequest


router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/notifications", response_model=NotificationSettingsResponse)
def get_notification_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = (
        db.query(NotificationSettings)
        .filter(NotificationSettings.user_id == user.id)
        .first()
    )
    if not settings:
        settings = NotificationSettings(
            user_id=user.id,
            fortune_enabled=True,
            diary_enabled=True,
            fortune_time="08:00:00",
            diary_time="20:00:00",
            device_tokens=[],
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


@router.put("/notifications", response_model=NotificationSettingsResponse)
def update_notification_settings(
    data: NotificationSettingsUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = (
        db.query(NotificationSettings)
        .filter(NotificationSettings.user_id == user.id)
        .first()
    )
    if not settings:
        settings = NotificationSettings(user_id=user.id)
        db.add(settings)

    if data.fortune_enabled is not None:
        settings.fortune_enabled = data.fortune_enabled
    if data.diary_enabled is not None:
        settings.diary_enabled = data.diary_enabled
    if data.fortune_time is not None:
        settings.fortune_time = data.fortune_time
    if data.diary_time is not None:
        settings.diary_time = data.diary_time
    if data.device_tokens is not None:
        settings.device_tokens = data.device_tokens

    db.commit()
    db.refresh(settings)
    return settings
