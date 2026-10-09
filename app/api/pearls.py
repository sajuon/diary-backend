from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.pearl import CheckInResponse, FortuneCookieInfo, FortuneCookieResponse
from app.services.fortune_cookie_message import generate_cookie_message
from app.services.pearls import (
    COOKIE_FREE,
    COOKIE_PAID,
    FORTUNE_COOKIE_PRICE,
    FORTUNE_COOKIE_TABLE,
    FREE_COOKIE_TABLE,
    REWARD_ATTENDANCE,
    CookieError,
    award_daily,
    check_can_open_cookie,
    cookie_to_dict,
    get_today_cookies,
    open_fortune_cookie,
    recent_cookie_messages,
)

router = APIRouter(prefix="/api/pearls", tags=["Pearls"])

COOKIE_ERRORS = {
    "already_opened": (409, "오늘은 이미 열었어요. 내일 또 열 수 있어요."),
    "not_enough_pearls": (400, "진주가 부족해요"),
}


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
def fortune_cookie_info(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """가격, 확률표, 오늘 연 쿠키(무료/상점)."""
    today = get_today_cookies(db, user.id)
    return {
        "price": FORTUNE_COOKIE_PRICE,
        "table": [{"amount": a, "chance": c} for a, c in FORTUNE_COOKIE_TABLE],
        "free_table": [{"amount": a, "chance": c} for a, c in FREE_COOKIE_TABLE],
        "today_free": cookie_to_dict(today[COOKIE_FREE]) if COOKIE_FREE in today else None,
        "today_paid": cookie_to_dict(today[COOKIE_PAID]) if COOKIE_PAID in today else None,
    }


async def _open(kind: str, user: User, db: Session) -> dict:
    try:
        check_can_open_cookie(db, user.id, kind)
        message, source = await generate_cookie_message(recent_cookie_messages(db, user.id))
        return open_fortune_cookie(db, user.id, kind, message, source)
    except CookieError as e:
        status, detail = COOKIE_ERRORS[e.code]
        raise HTTPException(status_code=status, detail=detail)


@router.post("/fortune-cookie", response_model=FortuneCookieResponse)
async def buy_fortune_cookie(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """상점 포춘쿠키: 5진주, 하루 1개."""
    return await _open(COOKIE_PAID, user, db)


@router.post("/fortune-cookie/free", response_model=FortuneCookieResponse)
async def open_free_fortune_cookie(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """오늘의 포춘쿠키: 무료, 하루 1개."""
    return await _open(COOKIE_FREE, user, db)
