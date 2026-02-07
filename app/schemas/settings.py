from datetime import datetime, time
from typing import Optional, List, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _parse_time(v) -> time:
    if v is None:
        return v
    if isinstance(v, time):
        return v
    if isinstance(v, str):
        # "HH:MM" or "HH:MM:SS"
        parts = v.strip().split(":")
        if len(parts) == 2:
            h, m = parts
            return time(hour=int(h), minute=int(m), second=0)
        if len(parts) == 3:
            h, m, s = parts
            return time(hour=int(h), minute=int(m), second=int(s))
    raise ValueError("time 형식은 'HH:MM' 또는 'HH:MM:SS' 이어야 합니다.")


class NotificationSettingsUpdateRequest(BaseModel):
    fortune_enabled: Optional[bool] = None
    diary_enabled: Optional[bool] = None

    fortune_time: Optional[Union[str, time]] = None
    diary_time: Optional[Union[str, time]] = None

    device_tokens: Optional[List[str]] = None

    _v1 = field_validator("fortune_time", mode="before")(_parse_time)
    _v2 = field_validator("diary_time", mode="before")(_parse_time)


class NotificationSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int

    fortune_enabled: bool
    diary_enabled: bool

    fortune_time: time
    diary_time: time

    device_tokens: Optional[List[str]] = None

    created_at: datetime
    updated_at: datetime
