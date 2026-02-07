from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.profile import UserBirthProfile
from app.models.fortune import DailyFortune
from app.schemas.fortune import DailyFortuneResponse
from app.services.fortune_generator import generate_daily_fortune  # 다음 단계에서 구현


router = APIRouter(prefix="/api/fortune", tags=["Fortune"])


def kst_today_date():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


@router.get("/today", response_model=DailyFortuneResponse)
def get_today_fortune(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today_date()

    fortune = (
        db.query(DailyFortune)
        .filter(DailyFortune.user_id == user.id, DailyFortune.fortune_date == today)
        .first()
    )
    if fortune:
        return fortune

    profile = db.query(UserBirthProfile).filter(UserBirthProfile.user_id == user.id).first()

    # 생성(멱등) - 서비스에서 문장 생성
    data = generate_daily_fortune(user=user, profile=profile, fortune_date=today)

    fortune = DailyFortune(
        user_id=user.id,
        fortune_date=today,
        love=data.get("love", ""),
        study=data.get("study", ""),
        caution=data.get("caution", ""),
        good_thing=data.get("good_thing", ""),
        ritual=data.get("ritual", ""),
        element_hint=data.get("element_hint"),
        model=data.get("model"),
    )
    db.add(fortune)
    db.commit()
    db.refresh(fortune)
    return fortune


@router.get("", response_model=list[DailyFortuneResponse])
def list_fortunes(
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 문자열로 받아도 되고, schemas/validator로 date 변환해도 됨
    fortunes = (
        db.query(DailyFortune)
        .filter(
            DailyFortune.user_id == user.id,
            DailyFortune.fortune_date >= from_date,
            DailyFortune.fortune_date <= to_date,
        )
        .order_by(DailyFortune.fortune_date.desc())
        .all()
    )
    return fortunes
