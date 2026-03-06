from datetime import date, datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, ConfigDict


class OtterLetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    diary_entry_id: int
    letter_date: date

    content: str
    element_hint: Optional[Dict[str, Any]] = None
    model: Optional[str] = None

    is_read: bool
    read_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime