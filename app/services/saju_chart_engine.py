# app/services/saju_chart_engine.py
# 역할:
# - 사용자 생년월일시를 기반으로 사주 원국(연주/월주/일주/시주)을 계산한다.
# - 일간, 오행 분포, 강한 오행/약한 오행 정보를 반환한다.
# - 오늘 날짜의 일진(오늘의 간지) 계산 함수도 함께 제공한다.

from __future__ import annotations

from datetime import date, time
from typing import Any, Dict, Optional

from app.models.profile import UserBirthProfile


HEAVENLY_STEMS = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
EARTHLY_BRANCHES = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

STEM_ELEMENTS = {
    "갑": {"element": "목", "yin_yang": "양"},
    "을": {"element": "목", "yin_yang": "음"},
    "병": {"element": "화", "yin_yang": "양"},
    "정": {"element": "화", "yin_yang": "음"},
    "무": {"element": "토", "yin_yang": "양"},
    "기": {"element": "토", "yin_yang": "음"},
    "경": {"element": "금", "yin_yang": "양"},
    "신": {"element": "금", "yin_yang": "음"},
    "임": {"element": "수", "yin_yang": "양"},
    "계": {"element": "수", "yin_yang": "음"},
}

BRANCH_ELEMENTS = {
    "자": {"element": "수", "yin_yang": "양"},
    "축": {"element": "토", "yin_yang": "음"},
    "인": {"element": "목", "yin_yang": "양"},
    "묘": {"element": "목", "yin_yang": "음"},
    "진": {"element": "토", "yin_yang": "양"},
    "사": {"element": "화", "yin_yang": "음"},
    "오": {"element": "화", "yin_yang": "양"},
    "미": {"element": "토", "yin_yang": "음"},
    "신": {"element": "금", "yin_yang": "양"},
    "유": {"element": "금", "yin_yang": "음"},
    "술": {"element": "토", "yin_yang": "양"},
    "해": {"element": "수", "yin_yang": "음"},
}

BRANCH_HIDDEN_STEMS = {
    "자": ["계"],
    "축": ["기", "계", "신"],
    "인": ["갑", "병", "무"],
    "묘": ["을"],
    "진": ["무", "을", "계"],
    "사": ["병", "무", "경"],
    "오": ["정", "기"],
    "미": ["기", "정", "을"],
    "신": ["경", "임", "무"],
    "유": ["신"],
    "술": ["무", "신", "정"],
    "해": ["임", "갑"],
}


def _julian_day_number(d: date) -> int:
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + ((153 * m + 2) // 5) + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def _year_pillar_index(birth_date: date) -> int:
    saju_year = birth_date.year

    # 입춘 기준 간단 보정
    if (birth_date.month, birth_date.day) < (2, 4):
        saju_year -= 1

    # 1984년 갑자년 기준
    return (saju_year - 1984) % 60


def _month_branch_index(birth_date: date) -> int:
    md = (birth_date.month, birth_date.day)

    if md >= (12, 7):
        branch = "자"
    elif md >= (11, 7):
        branch = "해"
    elif md >= (10, 8):
        branch = "술"
    elif md >= (9, 8):
        branch = "유"
    elif md >= (8, 8):
        branch = "신"
    elif md >= (7, 7):
        branch = "미"
    elif md >= (6, 6):
        branch = "오"
    elif md >= (5, 6):
        branch = "사"
    elif md >= (4, 5):
        branch = "진"
    elif md >= (3, 6):
        branch = "묘"
    elif md >= (2, 4):
        branch = "인"
    elif md >= (1, 6):
        branch = "축"
    else:
        branch = "자"

    return EARTHLY_BRANCHES.index(branch)


def _month_pillar_index(birth_date: date, year_stem_index: int) -> int:
    branch_index = _month_branch_index(birth_date)
    month_order_from_in = (branch_index - EARTHLY_BRANCHES.index("인")) % 12

    # 갑/기년 병인월 시작 규칙
    stem_index = (year_stem_index * 2 + 2 + month_order_from_in) % 10

    for i in range(60):
        if i % 10 == stem_index and i % 12 == branch_index:
            return i

    return 0


def _day_pillar_index(target_date: date) -> int:
    # 2024-02-10 갑진일 기준 보정
    jdn = _julian_day_number(target_date)
    return (jdn + 49) % 60


def _hour_branch_index(birth_time: Optional[time]) -> int:
    if birth_time is None:
        return -1

    hour = birth_time.hour

    if hour == 23 or hour == 0:
        return 0
    if 1 <= hour <= 2:
        return 1
    if 3 <= hour <= 4:
        return 2
    if 5 <= hour <= 6:
        return 3
    if 7 <= hour <= 8:
        return 4
    if 9 <= hour <= 10:
        return 5
    if 11 <= hour <= 12:
        return 6
    if 13 <= hour <= 14:
        return 7
    if 15 <= hour <= 16:
        return 8
    if 17 <= hour <= 18:
        return 9
    if 19 <= hour <= 20:
        return 10

    return 11


def _hour_pillar_index(day_stem_index: int, birth_time: Optional[time]) -> Optional[int]:
    branch_index = _hour_branch_index(birth_time)

    if branch_index < 0:
        return None

    stem_index = ((day_stem_index % 5) * 2 + branch_index) % 10

    for i in range(60):
        if i % 10 == stem_index and i % 12 == branch_index:
            return i

    return None


def _pillar_object(label: str, index: Optional[int]) -> Dict[str, Any]:
    if index is None:
        return {
            "label": label,
            "stem": None,
            "branch": None,
            "ganji": None,
            "stem_element": None,
            "branch_element": None,
            "hidden_stems": [],
        }

    stem = HEAVENLY_STEMS[index % 10]
    branch = EARTHLY_BRANCHES[index % 12]

    return {
        "label": label,
        "stem": stem,
        "branch": branch,
        "ganji": stem + branch,
        "stem_element": STEM_ELEMENTS[stem],
        "branch_element": BRANCH_ELEMENTS[branch],
        "hidden_stems": BRANCH_HIDDEN_STEMS.get(branch, []),
    }


def _count_elements(pillars: list[Dict[str, Any]]) -> Dict[str, float]:
    counts = {"목": 0.0, "화": 0.0, "토": 0.0, "금": 0.0, "수": 0.0}

    for pillar in pillars:
        stem = pillar.get("stem")
        branch = pillar.get("branch")

        if stem:
            counts[STEM_ELEMENTS[stem]["element"]] += 1.0

        if branch:
            counts[BRANCH_ELEMENTS[branch]["element"]] += 1.0

        for hidden in pillar.get("hidden_stems", []):
            if hidden in STEM_ELEMENTS:
                counts[STEM_ELEMENTS[hidden]["element"]] += 0.5

    return counts


def build_day_pillar(target_date: date) -> Dict[str, Any]:
    """
    오늘 날짜의 일진을 계산한다.
    saju_focus_engine에서 오늘의 흐름을 잡을 때 사용한다.
    """

    index = _day_pillar_index(target_date)
    return _pillar_object("today", index)


def build_saju_chart(profile: Optional[UserBirthProfile]) -> Dict[str, Any]:
    if not profile or not profile.birth_date:
        return {
            "chart_provided": False,
            "reason": "birth_date_missing",
            "pillars": [],
            "elementSummary": {},
            "dayMaster": None,
        }

    birth_date = profile.birth_date
    birth_time = profile.birth_time

    year_index = _year_pillar_index(birth_date)
    year_stem_index = year_index % 10

    month_index = _month_pillar_index(birth_date, year_stem_index)
    day_index = _day_pillar_index(birth_date)
    hour_index = _hour_pillar_index(day_index % 10, birth_time)

    pillars = [
        _pillar_object("year", year_index),
        _pillar_object("month", month_index),
        _pillar_object("day", day_index),
        _pillar_object("hour", hour_index),
    ]

    day_stem = pillars[2]["stem"]
    element_counts = _count_elements(pillars)

    strongest = max(element_counts, key=element_counts.get)
    weakest = min(element_counts, key=element_counts.get)

    return {
        "chart_provided": True,
        "calendar": "solar",
        "birth": {
            "date": birth_date.isoformat(),
            "time": birth_time.strftime("%H:%M") if birth_time else None,
            "timezone": getattr(profile, "timezone", None) or "Asia/Seoul",
            "place": getattr(profile, "birth_place", None),
            "sex": getattr(profile, "sex", None),
        },
        "pillars": pillars,
        "dayMaster": {
            "stem": day_stem,
            "element": STEM_ELEMENTS[day_stem]["element"] if day_stem else None,
            "yin_yang": STEM_ELEMENTS[day_stem]["yin_yang"] if day_stem else None,
        },
        "elementSummary": {
            "counts": element_counts,
            "strongest": strongest,
            "weakest": weakest,
        },
        "calculation_note": "입춘 및 절기 기준은 서비스용 간단 계산이며, 정밀 만세력과 1일 내외 차이가 있을 수 있습니다.",
    }