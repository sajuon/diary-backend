from datetime import date
from typing import Dict, Optional

from app.models.profile import UserBirthProfile


def analyze_daily_element_flow(
    profile: Optional[UserBirthProfile],
    target_date: date,
) -> Dict[str, str]:
    """
    사주를 '설명'하지 않고
    오늘의 흐름/리듬 힌트만 반환하는 용도
    """

    if profile is None or profile.birth_date is None:
        return {
            "dominant": "unknown",
            "message": "오늘은 흐름을 가볍게 느껴보는 게 좋아요."
        }

    # ⚠️ 지금은 날짜 기반 더미 로직
    day = target_date.day % 5

    element_map = {
        0: ("wood", "오늘은 시작과 시도가 잘 어울리는 날이에요."),
        1: ("fire", "감정이 쉽게 올라오는 하루일 수 있어요."),
        2: ("earth", "속도를 줄이고 균형을 잡기 좋은 날이에요."),
        3: ("metal", "생각이 많아질 수 있는 날이에요."),
        4: ("water", "감정과 생각이 깊어지기 쉬운 날이에요."),
    }

    dominant, msg = element_map[day]

    return {
        "dominant": dominant,
        "message": msg,
    }
