from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    push_enabled: bool
    fortune_enabled: bool
    diary_reminder_enabled: bool
    reply_enabled: bool
    timezone: str

    created_at: datetime
    updated_at: datetime


class NotificationSettingsUpdate(BaseModel):
    push_enabled: bool
    fortune_enabled: bool
    diary_reminder_enabled: bool
    reply_enabled: bool
    timezone: str = "Asia/Seoul"