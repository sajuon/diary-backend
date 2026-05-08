# app/services/saju_engine.py
# 역할:
# - 기존 코드에서 analyze_daily_element_flow를 import하는 곳이 있을 수 있어서 남겨두는 호환용 파일이다.
# - 더 이상 날짜 % 5 더미 로직을 사용하지 않는다.
# - 신규 사주 상세 해석은 saju_focus_engine.py의 build_saju_focus_points를 사용한다.

from __future__ import annotations

from datetime import date
from typing import Dict, Optional

from app.models.profile import UserBirthProfile
from app.services.saju_chart_engine import build_saju_chart
from app.services.saju_focus_engine import build_saju_focus_points


def analyze_daily_element_flow(
    profile: Optional[UserBirthProfile],
    target_date: date,
) -> Dict[str, str]:
    """
    legacy 호환용 함수.
    신규 상세 사주 해석에서는 직접 사용하지 않는 것을 권장한다.
    """

    if profile is None or profile.birth_date is None:
        return {
            "dominant": "unknown",
            "message": "오늘은 큰 흐름 중심으로 참고해 주세요.",
        }

    chart_payload = build_saju_chart(profile)
    focus_points = build_saju_focus_points(chart_payload, target_date)

    relation = focus_points.get("relation") or {}

    return {
        "dominant": str(focus_points.get("today_element") or "unknown"),
        "message": str(focus_points.get("summary") or ""),
        "theme": str(relation.get("theme") or ""),
        "relation_label": str(relation.get("label") or ""),
    }