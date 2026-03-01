from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, Literal


class RegisterRequest(BaseModel):
    # email is optional because we support social login; legacy accounts may still use it
    email: Optional[EmailStr] = None
    password: str = Field(min_length=6, max_length=128)
    nickname: str = Field(min_length=1, max_length=50)


class ProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = Field(default=None, max_length=50)
    profile_image: Optional[str] = Field(default=None, max_length=255)


class UserResponse(BaseModel):
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


class OAuthLoginRequest(BaseModel):
    provider: Literal["kakao", "google"]
    code: str
    redirect_uri: Optional[str] = None
