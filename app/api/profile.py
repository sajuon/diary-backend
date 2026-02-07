from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.profile import UserBirthProfile
from app.schemas.profile import UserBirthProfileResponse, UserBirthProfileUpdateRequest


router = APIRouter(prefix="/api/profile", tags=["Profile"])


@router.get("/birth", response_model=UserBirthProfileResponse)
def get_birth_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(UserBirthProfile).filter(UserBirthProfile.user_id == user.id).first()
    if not profile:
        # 없으면 빈 형태 반환을 원하면 schemas에서 optional로 처리하거나,
        # 여기서 기본 레코드 생성 정책을 선택할 수 있음
        profile = UserBirthProfile(
            user_id=user.id,
            birth_date=None,
            birth_time=None,
            birth_place=None,
            sex=None,
            timezone="Asia/Seoul",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return profile


@router.put("/birth", response_model=UserBirthProfileResponse)
def upsert_birth_profile(
    data: UserBirthProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(UserBirthProfile).filter(UserBirthProfile.user_id == user.id).first()

    if not profile:
        profile = UserBirthProfile(user_id=user.id)
        db.add(profile)

    # 업데이트
    profile.birth_date = data.birth_date
    profile.birth_time = data.birth_time
    profile.birth_place = data.birth_place
    profile.sex = data.sex
    profile.timezone = data.timezone or "Asia/Seoul"

    db.commit()
    db.refresh(profile)
    return profile