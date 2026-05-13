# /home/dori/diary-backend/app/schemas/diary.py

from datetime import date, datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, ConfigDict, Field


DiaryType = Literal["question", "free"]


class DiaryCreateRequest(BaseModel):
    entry_date: Optional[date] = None

    content: str = Field(min_length=1)

    weather: Optional[str] = None

    mood_tags: Optional[List[str]] = None

    # question: 질문형 일기
    # free: 자유 일기
    # 하루에 question 1개 + free 1개까지 가능
    diary_type: DiaryType = "free"

    # 질문형 일기 고정 ID
    # 예: 03-01, 05-12
    # 자유형이면 None으로 저장
    question_id: Optional[str] = None

    # 질문형 일기일 때 오늘의 질문 문구
    # 자유형이면 None으로 저장
    question_text: Optional[str] = None


class DiaryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int

    entry_date: date

    content: str

    weather: Optional[str] = None

    mood_tags: Optional[List[str]] = None

    summary_tag: Optional[str] = None

    diary_type: DiaryType = "free"

    question_id: Optional[str] = None

    question_text: Optional[str] = None

    created_at: datetime
    updated_at: datetime