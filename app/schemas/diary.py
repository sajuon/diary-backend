from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class DiaryCreateRequest(BaseModel):
    entry_date: Optional[date] = None

    content: str = Field(min_length=1)

    weather: Optional[str] = None

    mood_tags: Optional[List[str]] = None


class DiaryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int

    entry_date: date

    content: str

    weather: Optional[str] = None

    mood_tags: Optional[List[str]] = None

    summary_tag: Optional[str] = None

    created_at: datetime
    updated_at: datetime