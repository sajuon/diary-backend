from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.llm.payloads import build_base_payload
from app.models.profile import UserBirthProfile
from app.models.user import User
from app.services.letter_llm_service import LetterLLMError, request_letter_llm
from app.services.saju_engine import analyze_daily_element_flow

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


def _format_birth_date(profile: Optional[UserBirthProfile]) -> str:
    if not profile or not profile.birth_date:
        return "unknown"
    return profile.birth_date.isoformat()


def _format_birth_time(profile: Optional[UserBirthProfile]) -> str:
    if not profile or not profile.birth_time:
        return "unknown"
    return profile.birth_time.strftime("%H:%M")


def _profile_payload(profile: Optional[UserBirthProfile]) -> Dict[str, Any]:
    return {
        "calendar": "solar",
        "leap_month": False,
        "date": _format_birth_date(profile),
        "time": _format_birth_time(profile),
        "time_accuracy": "exact" if profile and profile.birth_time else "unknown",
        "timezone": str((profile.timezone if profile and profile.timezone else None) or "Asia/Seoul"),
        "place": {
            "country": "KR",
            "city": str((profile.birth_place if profile and profile.birth_place else None) or ""),
            "lat": 0.0,
            "lon": 0.0,
        },
    }


def _weekday_ko(target_date: date) -> str:
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    return weekdays[target_date.weekday()]


def _season_hint(target_date: date) -> str:
    month = target_date.month
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def _build_saju_payload(
    user: User,
    profile: Optional[UserBirthProfile],
    analysis_date: date,
) -> Dict[str, Any]:
    flow = analyze_daily_element_flow(profile, analysis_date)

    payload = build_base_payload(
        mode="saju_daily_analysis",
        user=user,
        birth_profile=_profile_payload(profile),
        chart=None,
        question=(
            f"{analysis_date.isoformat()} 기준으로 오늘과 가까운 시기의 흐름을 중심으로 "
            "성향, 일/학업, 금전, 관계, 컨디션을 자세히 풀어줘."
        ),
        topics=[
            "오늘의 흐름",
            "성향",
            "커리어/학업",
            "금전운",
            "연애/대인관계운",
            "건강/컨디션",
        ],
        tone="mystic",
        length="medium",
        structure="sections",
    )

    payload["user_profile"]["gender"] = str((profile.sex if profile and profile.sex else None) or "unknown")
    payload["current_context"] = {
        "as_of_date": analysis_date.isoformat(),
        "timezone": "Asia/Seoul",
        "weekday": _weekday_ko(analysis_date),
        "season": _season_hint(analysis_date),
        "app_surface": "saju_page",
    }
    payload["daily_flow_hint"] = {
        "dominant": flow.get("dominant", "unknown"),
        "message": flow.get("message", ""),
    }
    payload["input_quality"] = {
        "birth_date_provided": bool(profile and profile.birth_date),
        "birth_time_provided": bool(profile and profile.birth_time),
        "birth_place_provided": bool(profile and profile.birth_place),
        "chart_provided": False,
    }
    return payload


def _clean_analysis_text(text: str) -> str:
    cleaned = text.strip()
    fenced = re.search(r"```(?:text|markdown)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    cleaned = cleaned.strip().strip('"').strip("'")
    cleaned = re.sub(r"\r\n?", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _fallback_analysis(user: User, profile: Optional[UserBirthProfile], analysis_date: date) -> str:
    name = getattr(user, "nickname", None) or "해도리 친구"
    missing = []
    if not profile or not profile.birth_date:
        missing.append("생년월일")
    if not profile or not profile.birth_time:
        missing.append("출생시간")
    if not profile or not profile.birth_place:
        missing.append("출생지")

    missing_line = ""
    if missing:
        missing_line = f"입력 정보는 {', '.join(missing)}가 비어 있어 가능성 중심으로만 가볍게 읽을 수 있습니다.\n\n"

    return (
        "이 내용은 오락·참고용 해석입니다.\n\n"
        f"{name}님 기준 {analysis_date.isoformat()}의 흐름을 보면, 지금은 큰 결론을 서두르기보다 "
        "생활 리듬과 감정의 균형을 먼저 다듬는 편이 좋은 때로 읽힙니다.\n\n"
        f"{missing_line}"
        "오늘의 포인트는 무리한 확장보다 정리와 점검입니다. 일이나 공부에서는 한 번에 많이 밀어붙이기보다 "
        "우선순위를 좁히면 흐름이 안정되기 쉽고, 관계에서는 상대의 반응을 바로 단정하지 말고 한 템포 여유를 두는 편이 좋습니다.\n\n"
        "금전 쪽은 충동 지출이나 즉흥 결정만 조심하면 무난한 흐름에 가깝고, 컨디션은 수면과 피로 누적 신호를 먼저 살피는 쪽이 좋겠습니다.\n\n"
        "작게 실천할 팁으로는 아침에 오늘 할 일을 세 가지 안으로 줄여 적고, 저녁에는 쌓인 감정을 짧게 메모로 정리해보는 방법이 잘 맞습니다."
    )


async def generate_saju_analysis(
    user: User,
    profile: Optional[UserBirthProfile],
    *,
    analysis_date: Optional[date] = None,
) -> Dict[str, Any]:
    target_date = analysis_date or datetime.now(KST).date()
    request_object = _build_saju_payload(user, profile, target_date)

    payload = {
        "model": settings.SAJU_LLM_MODEL,
        "messages": [
            # The saju-v0 OpenWebUI preset already carries the long-form rules.
            {
                "role": "user",
                "content": json.dumps(request_object, ensure_ascii=False, separators=(",", ":")),
            },
        ],
        "temperature": 0.65,
        "max_tokens": 700,
        "_request_options": {
            "timeout_sec": 25,
            "strategy_allowlist": [
                "openwebui-openai",
                "explicit-openwebui-openai",
            ],
        },
    }

    try:
        logger.info(
            "[SAJU_ANALYSIS] requesting LLM. user_id=%s date=%s model=%s",
            getattr(user, "id", None),
            target_date,
            settings.SAJU_LLM_MODEL,
        )
        llm_resp = await request_letter_llm(payload)
        content = llm_resp.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LetterLLMError("Saju LLM 응답에 content 없음")

        cleaned = _clean_analysis_text(content)
        if not cleaned:
            raise LetterLLMError("Saju LLM 응답 정리 후 빈 문자열")

        logger.info(
            "[SAJU_ANALYSIS] LLM success. user_id=%s date=%s model=%s",
            getattr(user, "id", None),
            target_date,
            llm_resp.get("model") or settings.SAJU_LLM_MODEL,
        )
        return {
            "analysis": cleaned,
            "analysis_date": target_date.isoformat(),
            "model": llm_resp.get("model") or settings.SAJU_LLM_MODEL,
            "chart_provided": False,
            "pillars": [],
            "elementSummary": {},
        }
    except LetterLLMError as exc:
        logger.warning(
            "[SAJU_ANALYSIS] fallback triggered. user_id=%s date=%s reason=%s",
            getattr(user, "id", None),
            target_date,
            str(exc),
        )
        return {
            "analysis": _fallback_analysis(user, profile, target_date),
            "analysis_date": target_date.isoformat(),
            "model": "rule-based-saju-fallback",
            "chart_provided": False,
            "pillars": [],
            "elementSummary": {},
        }
