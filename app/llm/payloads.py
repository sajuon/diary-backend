# backend/app/llm/payloads.py
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo


def build_base_payload(
    *,
    mode: str,
    user,
    birth_profile: dict | None,
    chart: dict | None,
    question: str,
    topics: list[str] | None = None,
    tone: str = "friendly",
    length: str = "medium",
    structure: str = "sections",
):
    topics = topics or []

    # birth_profile이 아직 없을 수도 있으니까(유저가 생일 입력 안했을 때) 안전하게 디폴트
    birth = {
        "calendar": "unknown",
        "leap_month": False,
        "date": "2000-01-01",
        "time": "00:00",
        "time_accuracy": "unknown",
        "timezone": "Asia/Seoul",
        "place": {"country": "KR", "city": "", "lat": 0.0, "lon": 0.0},
    }

    if birth_profile:
        # 네 DB 구조에 맞게 key 이름만 맞춰주면 됨
        birth = {
            "calendar": birth_profile.get("calendar", "solar") or "solar",
            "leap_month": bool(birth_profile.get("leap_month", False)),
            "date": birth_profile.get("date", "2000-01-01"),
            "time": birth_profile.get("time", "00:00"),
            "time_accuracy": birth_profile.get("time_accuracy", "unknown"),
            "timezone": birth_profile.get("timezone", "Asia/Seoul") or "Asia/Seoul",
            "place": birth_profile.get(
                "place",
                {"country": "KR", "city": "", "lat": 0.0, "lon": 0.0},
            ),
        }

    return {
        "schema_version": "1.0",
        "request_id": str(uuid.uuid4()),
        "lang": "ko",
        "mode": mode,
        "user_profile": {
            "display_name": getattr(user, "nickname", None) or getattr(user, "display_name", None) or "해도리 친구",
            "gender": getattr(user, "gender", None) or "unknown",
            "notes": "",
        },
        "birth": birth,
        "chart": chart
        or {
            "provided": False,
            "pillars": {
                "year": {"heavenly_stem": "", "earthly_branch": ""},
                "month": {"heavenly_stem": "", "earthly_branch": ""},
                "day": {"heavenly_stem": "", "earthly_branch": ""},
                "hour": {"heavenly_stem": "", "earthly_branch": ""},
            },
            "day_master": "",
            "five_elements": {"wood": 0, "fire": 0, "earth": 0, "metal": 0, "water": 0},
            "yin_yang_balance": {"yin": 0, "yang": 0},
            "ten_gods_summary": {
                "bi_gyeon": 0,
                "geop_jae": 0,
                "sik_sin": 0,
                "sang_gwan": 0,
                "pyeon_jae": 0,
                "jeong_jae": 0,
                "pyeon_gwan": 0,
                "jeong_gwan": 0,
                "pyeon_in": 0,
                "jeong_in": 0,
            },
            "useful_god": {"yong_sin": "", "hui_sin": "", "gi_sin": ""},
            "luck_cycles": {"dae_woon": [], "se_woon": [], "monthly": []},
            "special_stars": {
                "peach_blossom": False,
                "travel_star": False,
                "nobleman_star": False,
                "academic_star": False,
                "robbery_star": False,
            },
        },
        "focus": {
            "topics": topics,
            "question": question,
            "horizon_months": 12,
            "risk_tolerance": "medium",
        },
        "output_prefs": {
            "tone": tone,
            "length": length,
            "structure": structure,
            "include_action_tips": True,
            "include_dates": True,
        },
        "consent": {"entertainment_only_ack": True},
    }