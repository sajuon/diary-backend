from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel


class DiaryQuestionResponse(BaseModel):
    question: str
    model: Optional[str] = None
    source_type: str
    entry_date: date
    created_at: datetime
    cached: bool = False

    class Config:
        from_attributes = True