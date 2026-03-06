from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.notification_settings import NotificationSettings
from app.models.user import User
from app.schemas.settings import (
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
)

router = APIRouter(prefix="/api/settings", tags=["Settings"])


def get_or_create_notification_settings(
    db: Session,
    user_id: int,
) -> NotificationSettings:
    settings = (
        db.query(NotificationSettings)
        .filter(NotificationSettings.user_id == user_id)
        .first()
    )

    if settings:
        return settings

    settings = NotificationSettings(
        user_id=user_id,
        push_enabled=True,
        fortune_enabled=True,
        diary_reminder_enabled=True,
        reply_enabled=True,
        timezone="Asia/Seoul",
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/notifications", response_model=NotificationSettingsResponse)
def get_notification_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_or_create_notification_settings(db, user.id)
    return settings


@router.put("/notifications", response_model=NotificationSettingsResponse)
def update_notification_settings(
    data: NotificationSettingsUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_or_create_notification_settings(db, user.id)

    if data.push_enabled is not None:
        settings.push_enabled = data.push_enabled

    if data.fortune_enabled is not None:
        settings.fortune_enabled = data.fortune_enabled

    if data.diary_reminder_enabled is not None:
        settings.diary_reminder_enabled = data.diary_reminder_enabled

    if data.reply_enabled is not None:
        settings.reply_enabled = data.reply_enabled

    if data.timezone is not None:
        settings.timezone = data.timezone

    db.commit()
    db.refresh(settings)
    return settings