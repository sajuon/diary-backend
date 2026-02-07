from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    nickname: str = Field(min_length=1, max_length=50)


class ProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = Field(default=None, max_length=50)
    profile_image: Optional[str] = Field(default=None, max_length=255)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nickname: str
    profile_image: Optional[str] = None
    created_at: datetime
    updated_at: datetime
