# 기존 파일 경로: /home/dori/diary-backend/app/api/saju.py
# 수정 파일 경로: /home/dori/diary-backend/app/api/saju.py
# 역할: 사주/운세 API 라우터. 오늘의 운세, 연애운, 재물운, 학업운 type을 받아 서로 다른 해석을 생성/반환한다.

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.fortune import DailySajuAnalysis
from app.models.profile import UserBirthProfile
from app.models.user import User
from app.services.saju_analysis_service import generate_saju_analysis
from app.services.pearls import REWARD_FORTUNE, award_daily

router = APIRouter(prefix="/api/saju", tags=["Saju"])

ALLOWED_FORTUNE_TYPES = {"daily", "love", "money", "study"}


def kst_today_date():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


@router.get("/manse")
async def get_manse(
    type: str = Query(default="daily"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = await _get_manse(type=type, user=user, db=db)

    # 운세 보기 보상: 오늘의 하루/사주 운세 통틀어 하루 1번
    if isinstance(result, dict):
        result["pearl_reward"] = award_daily(db, user.id, REWARD_FORTUNE)

    return result


async def _get_manse(
    type: str = Query(default="daily"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today_date()

    fortune_type = (type or "daily").strip().lower()
    if fortune_type not in ALLOWED_FORTUNE_TYPES:
        fortune_type = "daily"

    profile = (
        db.query(UserBirthProfile)
        .filter(UserBirthProfile.user_id == user.id)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="생년월일시를 먼저 등록해주세요",
        )

    existing = (
        db.query(DailySajuAnalysis)
        .filter(
            DailySajuAnalysis.user_id == user.id,
            DailySajuAnalysis.analysis_date == today,
        )
        .first()
    )

    # 현재 DB는 날짜당 1개만 저장하는 구조일 가능성이 높아서,
    # daily만 캐시를 사용하고 love/money/study는 매번 새로 생성해서 반환한다.
    # 나중에 fortune_type 컬럼을 추가하면 type별 캐시 저장으로 확장 가능하다.
    if fortune_type == "daily" and existing and "rule-based" not in (existing.model or ""):
        return {
            "analysis": existing.analysis,
            "analysis_date": existing.analysis_date.isoformat(),
            "model": existing.model,
            "chart_provided": existing.chart_provided,
            "pillars": existing.pillars or [],
            "elementSummary": existing.element_summary or {},
            "saju_focus_points": existing.saju_focus_points or {},
            "fortune_type": fortune_type,
            "cached": True,
        }

    if fortune_type == "daily" and existing and "rule-based" in (existing.model or ""):
        db.delete(existing)
        db.commit()

    data = await generate_saju_analysis(
        user=user,
        profile=profile,
        analysis_date=today,
        fortune_type=fortune_type,
    )

    data["fortune_type"] = fortune_type

    # daily 외 type은 현재 테이블 구조상 저장하지 않고 바로 반환한다.
    if fortune_type != "daily":
        return {
            **data,
            "cached": False,
        }

    # rule-based fallback이면 저장하지 않는다.
    if "rule-based" in (data.get("model") or ""):
        return {
            **data,
            "cached": False,
        }

    saju_analysis = DailySajuAnalysis(
        user_id=user.id,
        analysis_date=today,
        analysis=data.get("analysis", ""),
        model=data.get("model"),
        chart_provided=bool(data.get("chart_provided")),
        pillars=data.get("pillars") or [],
        element_summary=data.get("elementSummary") or {},
        saju_focus_points=data.get("saju_focus_points") or {},
    )

    try:
        db.add(saju_analysis)
        db.commit()
        db.refresh(saju_analysis)

        return {
            "analysis": saju_analysis.analysis,
            "analysis_date": saju_analysis.analysis_date.isoformat(),
            "model": saju_analysis.model,
            "chart_provided": saju_analysis.chart_provided,
            "pillars": saju_analysis.pillars or [],
            "elementSummary": saju_analysis.element_summary or {},
            "saju_focus_points": saju_analysis.saju_focus_points or {},
            "fortune_type": fortune_type,
            "cached": False,
        }

    except IntegrityError:
        db.rollback()

        latest = (
            db.query(DailySajuAnalysis)
            .filter(
                DailySajuAnalysis.user_id == user.id,
                DailySajuAnalysis.analysis_date == today,
            )
            .first()
        )

        if latest:
            return {
                "analysis": latest.analysis,
                "analysis_date": latest.analysis_date.isoformat(),
                "model": latest.model,
                "chart_provided": latest.chart_provided,
                "pillars": latest.pillars or [],
                "elementSummary": latest.element_summary or {},
                "saju_focus_points": latest.saju_focus_points or {},
                "fortune_type": fortune_type,
                "cached": True,
            }

        raise