from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    # email is optional because we support social login; legacy accounts may still use it
    email: Optional[EmailStr] = None
    password: str = Field(min_length=6, max_length=128)
    nickname: str = Field(min_length=1, max_length=50)


class ProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = Field(default=None, max_length=50)
    profile_image: Optional[str] = Field(default=None, max_length=255)


class UserResponse(BaseModel):
    """
    /api/users/me 응답 스키마

    streak_n: 홈 우측 숫자 + 마이페이지 연속일에 그대로 표시될 n
    has_today: 홈 문구 분기용 (오늘 일기 작성 여부)
    total_diaries: 총 기록
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: Optional[str] = None
    nickname: str
    profile_image: Optional[str] = None
    provider: str
    provider_id: Optional[str] = None
    pearls: int
    created_at: datetime
    updated_at: datetime

    # ✅ streak fields
    streak_n: int = 0
    has_today: bool = False
    total_diaries: int = 0


class OAuthLoginRequest(BaseModel):
    provider: Literal["kakao", "google"]
    code: str
    redirect_uri: Optional[str] = None