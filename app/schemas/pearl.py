from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PearlReward(BaseModel):
    amount: int
    reason: str
    label: str
    balance: int


class CheckInResponse(BaseModel):
    pearls: int
    pearl_reward: Optional[PearlReward] = None


class TodayCookie(BaseModel):
    kind: Literal["free", "paid"]
    reward: int
    is_jackpot: bool
    message: str


class FortuneCookieResponse(TodayCookie):
    price: int
    balance: int


class CookieChance(BaseModel):
    amount: int
    chance: float


class FortuneCookieInfo(BaseModel):
    price: int
    table: list[CookieChance]
    free_table: list[CookieChance]
    today_free: Optional[TodayCookie] = None
    today_paid: Optional[TodayCookie] = None


class LetterFeedbackRequest(BaseModel):
    rating: Literal["like", "dislike"]
    comment: str = Field(default="", max_length=300)


class LetterFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    letter_id: int
    rating: Literal["like", "dislike"]
    comment: str
    created_at: datetime
    updated_at: datetime
    pearl_reward: Optional[PearlReward] = None
