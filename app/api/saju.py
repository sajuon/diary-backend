from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.fortune import DailySajuAnalysis
from app.models.profile import UserBirthProfile
from app.models.user import User
from app.services.saju_analysis_service import generate_saju_analysis

# 🔥 이게 반드시 먼저 있어야 함
router = APIRouter(prefix="/api/saju", tags=["Saju"])


def kst_today_date():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


@router.get("/manse")
async def get_manse(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today_date()

    existing = (
        db.query(DailySajuAnalysis)
        .filter(
            DailySajuAnalysis.user_id == user.id,
            DailySajuAnalysis.analysis_date == today,
        )
        .first()
    )

    # 🔥 정상 결과면 캐시 반환
    if existing and "rule-based" not in (existing.model or ""):
        return {
            "analysis": existing.analysis,
            "analysis_date": existing.analysis_date.isoformat(),
            "model": existing.model,
            "chart_provided": existing.chart_provided,
            "pillars": existing.pillars or [],
            "elementSummary": existing.element_summary or {},
            "saju_focus_points": existing.saju_focus_points or {},
            "cached": True,
        }

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

    # 🔥 기존 rule-based 삭제
    if existing and "rule-based" in (existing.model or ""):
        db.delete(existing)
        db.commit()

    data = await generate_saju_analysis(
        user=user,
        profile=profile,
        analysis_date=today,
    )

    # 🔥 rule-based면 저장 안 함
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
            "cached": False,
        }

    except IntegrityError:
        db.rollback()
        raise