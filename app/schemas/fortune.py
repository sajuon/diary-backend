from datetime import date, datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, ConfigDict

from app.schemas.pearl import PearlReward


class DailyFortuneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    fortune_date: date

    love: str
    study: str
    caution: str
    good_thing: str
    ritual: str

    element_hint: Optional[Dict[str, Any]] = None
    model: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    # 이번 요청으로 받은 진주 보상 (없으면 null)
    pearl_reward: Optional[PearlReward] = None
