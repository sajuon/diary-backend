from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class DiaryCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    mood_tags: Optional[List[str]] = None


class DiaryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    entry_date: date
    content: str
    mood_tags: Optional[List[str]] = None

    created_at: datetime
    updated_at: datetime
