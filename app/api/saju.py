from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.profile import UserBirthProfile

router = APIRouter(prefix="/api/saju", tags=["Saju"])

@router.get("/manse")
def get_manse(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(UserBirthProfile).filter(UserBirthProfile.user_id == user.id).first()
    if not profile or not profile.birth_date:
        return {"pillars": [], "elementSummary": {}}

    # 실제 사주 계산 로직 (간단 예시)
    birth_date = profile.birth_date
    birth_time = profile.birth_time
    stems = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
    branches = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]
    elements = ["목", "목", "화", "화", "토", "토", "금", "금", "수", "수"]
    tenGods = ["비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인"]

    y = birth_date.year % 10
    m = birth_date.month % 12
    d = birth_date.day % 10
    h = (birth_time.hour if birth_time else 0) % 10

    pillars = [
        {"label": "년", "stem": stems[y], "branch": branches[y], "tenGod": tenGods[y], "element": elements[y]},
        {"label": "월", "stem": stems[m], "branch": branches[m], "tenGod": tenGods[m], "element": elements[m]},
        {"label": "일", "stem": stems[d], "branch": branches[d], "tenGod": tenGods[d], "element": elements[d]},
        {"label": "시", "stem": stems[h], "branch": branches[h], "tenGod": tenGods[h], "element": elements[h]},
    ]
    elementSummary = {"화": 0, "수": 0, "목": 0, "금": 0, "토": 0}
    for p in pillars:
        elementSummary[p["element"]] += 1

    return {
        "pillars": pillars,
        "elementSummary": elementSummary
    }
