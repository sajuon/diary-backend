from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, time

from app.models.profile import UserBirthProfile


def get_birth_profile(db: Session, user_id: int) -> Optional[UserBirthProfile]:
    return db.query(UserBirthProfile).filter(UserBirthProfile.user_id == user_id).first()


def create_birth_profile(
    db: Session,
    user_id: int,
    birth_date: Optional[date],
    birth_time: Optional[time],
    birth_place: Optional[str],
    sex: Optional[str],
    timezone: str = "Asia/Seoul",
) -> UserBirthProfile:
    profile = UserBirthProfile(
        user_id=user_id,
        birth_date=birth_date,
        birth_time=birth_time,
        birth_place=birth_place,
        sex=sex,
        timezone=timezone,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def upsert_birth_profile(
    db: Session,
    user_id: int,
    birth_date: Optional[date],
    birth_time: Optional[time],
    birth_place: Optional[str],
    sex: Optional[str],
    timezone: Optional[str] = None,
) -> UserBirthProfile:
    profile = get_birth_profile(db, user_id)

    if not profile:
        profile = UserBirthProfile(user_id=user_id)
        db.add(profile)

    profile.birth_date = birth_date
    profile.birth_time = birth_time
    profile.birth_place = birth_place
    profile.sex = sex
    profile.timezone = timezone or "Asia/Seoul"

    db.commit()
    db.refresh(profile)
    return profile
