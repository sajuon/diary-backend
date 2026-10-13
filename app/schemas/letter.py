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
    is_favorite: bool
    read_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime


class OtterLetterFavoriteUpdateRequest(BaseModel):
    is_favorite: bool

class LetterRegenerateInfo(BaseModel):
    """답장 재생성 전 안내용 정보."""

    letter_id: int
    diary_entry_id: int
    letter_date: date
    # 기존 답장이 만들어진 뒤 일기를 수정했는지.
    # False면 FE에서 "일기를 수정하지 않았습니다. 재생성하시겠습니까?" 안내.
    diary_modified: bool
    cost: int
    pearls: int
