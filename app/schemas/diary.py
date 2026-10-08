# /home/dori/diary-backend/app/schemas/diary.py

from datetime import date, datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, ConfigDict, Field


DiaryType = Literal["question", "free"]

# 감정 조약돌 13종
# 프론트엔드 components/emotion-stone.tsx 의 EmotionKey 와 반드시 일치해야 함
# 순서: 긍정 -> 중립 -> 부정
MoodTag = Literal[
    "happy",
    "excited",
    "calm",
    "grateful",
    "proud",
    "neutral",
    "blank",
    "tired",
    "worried",
    "sad",
    "upset",
    "lonely",
    "angry",
]


class DiaryCreateRequest(BaseModel):
    entry_date: Optional[date] = None

    content: str = Field(min_length=1)

    weather: Optional[str] = None

    # 현재 프론트는 1개만 보내지만 배열 구조는 유지
    # 복수 선택(돌 두 개 올리기) 도입 시 max_length만 조정
    mood_tags: Optional[List[MoodTag]] = Field(default=None, max_length=2)

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

    # 주의: 여기는 MoodTag가 아니라 List[str] 로 둔다.
    # DB에 남아 있는 구버전 값("즐거움", "뿌듯함" 등)을 읽을 때
    # 응답 검증에서 500이 터지는 것을 막기 위함.
    # 입력은 좁게, 출력은 넓게.
    mood_tags: Optional[List[str]] = None

    summary_tag: Optional[str] = None

    diary_type: DiaryType = "free"

    question_id: Optional[str] = None

    question_text: Optional[str] = None

    created_at: datetime
    updated_at: datetime