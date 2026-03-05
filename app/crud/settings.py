from sqlalchemy.orm import Session
from typing import Optional, List

from app.models.settings import NotificationSettings


def get_notification_settings(db: Session, user_id: int) -> Optional[NotificationSettings]:
    return (
        db.query(NotificationSettings)
        .filter(NotificationSettings.user_id == user_id)
        .first()
    )


def create_default_settings(db: Session, user_id: int) -> NotificationSettings:
    settings = NotificationSettings(
        user_id=user_id,
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


def get_or_create_settings(db: Session, user_id: int) -> NotificationSettings:
    settings = get_notification_settings(db, user_id)
    if settings:
        return settings
    return create_default_settings(db, user_id)


def update_settings(
    db: Session,
    settings: NotificationSettings,
    fortune_enabled: Optional[bool] = None,
    diary_enabled: Optional[bool] = None,
    fortune_time: Optional[str] = None,
    diary_time: Optional[str] = None,
    device_tokens: Optional[List[str]] = None,
) -> NotificationSettings:
    if fortune_enabled is not None:
        settings.fortune_enabled = fortune_enabled
    if diary_enabled is not None:
        settings.diary_enabled = diary_enabled
    if fortune_time is not None:
        settings.fortune_time = fortune_time
    if diary_time is not None:
        settings.diary_time = diary_time
    if device_tokens is not None:
        settings.device_tokens = device_tokens

    db.commit()
    db.refresh(settings)
    return settings
