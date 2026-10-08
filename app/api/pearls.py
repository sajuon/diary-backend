from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.pearl import CheckInResponse, FortuneCookieInfo, FortuneCookieResponse
from app.services.pearls import (
    FORTUNE_COOKIE_PRICE,
    FORTUNE_COOKIE_TABLE,
    REWARD_ATTENDANCE,
    award_daily,
    open_fortune_cookie,
)

router = APIRouter(prefix="/api/pearls", tags=["Pearls"])


@router.post("/check-in", response_model=CheckInResponse)
def check_in(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """하루 첫 접속 출석 보상. 이미 받았으면 pearl_reward는 null."""
    reward = award_daily(db, user.id, REWARD_ATTENDANCE)
    pearls = reward["balance"] if reward else int(
        db.query(User.pearls).filter(User.id == user.id).scalar() or 0
    )
    return {"pearls": pearls, "pearl_reward": reward}


@router.get("/fortune-cookie", response_model=FortuneCookieInfo)
def fortune_cookie_info():
    return {
        "price": FORTUNE_COOKIE_PRICE,
        "table": [{"amount": a, "chance": c} for a, c in FORTUNE_COOKIE_TABLE],
    }


@router.post("/fortune-cookie", response_model=FortuneCookieResponse)
def buy_fortune_cookie(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = open_fortune_cookie(db, user.id)
    if result is None:
        raise HTTPException(status_code=400, detail="진주가 부족해요")
    return result
