from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    profile_image: Optional[str] = None
    created_at: datetime
