from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.profile import UserBirthProfile
from app.services.saju_analysis_service import generate_saju_analysis

router = APIRouter(prefix="/api/saju", tags=["Saju"])

@router.get("/manse")
async def get_manse(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(UserBirthProfile).filter(UserBirthProfile.user_id == user.id).first()
    return await generate_saju_analysis(user, profile)
