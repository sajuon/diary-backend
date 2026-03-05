from datetime import date, time, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserBirthProfileUpdateRequest(BaseModel):
    birth_date: Optional[date] = None
    birth_time: Optional[time] = None
    birth_place: Optional[str] = Field(default=None, max_length=100)
    sex: Optional[str] = Field(default=None, max_length=10)
    timezone: Optional[str] = Field(default="Asia/Seoul", max_length=50)


class UserBirthProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    birth_date: Optional[date] = None
    birth_time: Optional[time] = None
    birth_place: Optional[str] = None
    sex: Optional[str] = None
    timezone: str

    created_at: datetime
    updated_at: datetime
