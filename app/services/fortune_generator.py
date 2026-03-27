from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Dict, Optional

from app.core.config import settings
from app.models.profile import UserBirthProfile
from app.models.user import User
from app.services.letter_llm_service import LetterLLMError, request_letter_llm
from app.services.saju_engine import analyze_daily_element_flow

logger = logging.getLogger(__name__)


def format_date_str(target_date: date) -> str:
    return f"{target_date.year}. {target_date.month}. {target_date.day}."


def _build_fortune_system_prompt() -> str:
    return (
        "너는 해도리 앱의 오늘의 사주 흐름을 작성하는 안내자다.\n"
        "사용자에게 부담을 주지 않는 부드러운 한국어로, 하루의 흐름을 짧고 분명하게 정리한다.\n"
        "사주를 직접 설명하거나 단정적인 예언을 하지 않는다.\n"
        "운세 문구는 매일 조금씩 달라져야 하며, 딱딱한 템플릿 문장처럼 쓰지 않는다.\n"
        "\n"
        "[출력 규칙]\n"
        "- 반드시 JSON 객체 하나만 출력한다.\n"
        "- 마크다운, 코드블록, 설명 문장 금지.\n"
        "- 모든 값은 한국어 문자열이다.\n"
        "- 각 문장은 너무 길지 않게 1~2문장으로 쓴다.\n"
        "\n"
        "[JSON 키]\n"
        "keyword: 오늘의 흐름 키워드, 2~6글자 또는 짧은 구절\n"
        "summary: 오늘의 전체 흐름 설명, 2문장 이내\n"
        "love: 관계/감정 흐름 한 줄\n"
        "study: 일/공부/집중 흐름 한 줄\n"
        "caution: 조심할 것 한 줄\n"
        "good_thing: 기대해도 좋은 일 한 줄\n"
        "ritual: 오늘 해볼 작은 행동 한 줄\n"
        "dominant: wood, fire, earth, metal, water, unknown 중 하나\n"
    )


def _profile_hint(profile: Optional[UserBirthProfile]) -> Dict[str, str]:
    if not profile:
        return {
            "birth_date": "unknown",
            "birth_time": "unknown",
            "birth_place": "unknown",
            "sex": "unknown",
            "timezone": "Asia/Seoul",
        }

    return {
        "birth_date": str(profile.birth_date or "unknown"),
        "birth_time": str(profile.birth_time or "unknown"),
        "birth_place": str(profile.birth_place or "unknown"),
        "sex": str(profile.sex or "unknown"),
        "timezone": str(profile.timezone or "Asia/Seoul"),
    }


def _build_fortune_user_prompt(
    user: User,
    profile: Optional[UserBirthProfile],
    fortune_date: date,
    flow: Dict[str, str],
) -> str:
    profile_hint = _profile_hint(profile)

    return (
        f"닉네임: {getattr(user, 'nickname', None) or '사용자'}\n"
        f"대상 날짜: {format_date_str(fortune_date)}\n"
        f"오늘의 흐름 힌트: {flow.get('message', '')}\n"
        f"dominant 후보: {flow.get('dominant', 'unknown')}\n"
        f"생년월일: {profile_hint['birth_date']}\n"
        f"출생시간: {profile_hint['birth_time']}\n"
        f"출생지: {profile_hint['birth_place']}\n"
        f"성별: {profile_hint['sex']}\n"
        f"시간대: {profile_hint['timezone']}\n"
        "\n"
        "앱 화면에 들어갈 오늘의 사주 흐름을 JSON으로 만들어줘.\n"
        "keyword와 summary는 홈 화면 모달에 바로 쓰일 수 있게 자연스럽고 짧게 써줘.\n"
        "love, study, caution, good_thing, ritual은 각각 겹치지 않게 다른 관점으로 써줘."
    )


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON object not found in fortune response")

    return json.loads(cleaned[start : end + 1])


def _normalize_text(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    text = re.sub(r"\s+", " ", value).strip()
    return text or fallback


def _rule_based_fortune(flow: Dict[str, str]) -> Dict[str, Any]:
    dominant = flow.get("dominant", "unknown")
    message = flow.get("message") or "오늘은 흐름을 가볍게 느껴보는 게 좋아요."

    keyword_map = {
        "wood": "시작의 기운",
        "fire": "감정의 온도",
        "earth": "균형 잡기",
        "metal": "정리의 감각",
        "water": "깊은 호흡",
        "unknown": "부드러운 흐름",
    }

    return {
        "love": "가까운 사람과는 속도를 맞추듯 천천히 대화해보세요.",
        "study": "한 번에 많이 하려 하기보다 작은 단위로 나누면 흐름이 좋아져요.",
        "caution": "기분이 흔들리는 순간 바로 결론을 내리지 않는 게 좋아요.",
        "good_thing": "예상보다 따뜻한 말이나 작은 도움을 받을 수 있어요.",
        "ritual": "아침이나 오후에 물 한 잔 마시며 호흡을 고르면 좋겠어요.",
        "element_hint": {
            "dominant": dominant,
            "message": message,
            "keyword": keyword_map.get(dominant, keyword_map["unknown"]),
            "summary": message,
        },
        "model": "rule-based-fortune-fallback",
    }


async def generate_daily_fortune(
    user: User,
    profile: Optional[UserBirthProfile],
    fortune_date: date,
) -> Dict[str, Any]:
    """
    반환 값은 그대로 DB에 저장됨
    """
    flow = analyze_daily_element_flow(profile, fortune_date)
    dominant = flow.get("dominant", "unknown")

    payload = {
        "model": settings.FORTUNE_LLM_MODEL,
        "messages": [
            {"role": "system", "content": _build_fortune_system_prompt()},
            {
                "role": "user",
                "content": _build_fortune_user_prompt(
                    user=user,
                    profile=profile,
                    fortune_date=fortune_date,
                    flow=flow,
                ),
            },
        ],
        "temperature": 0.85,
        "max_tokens": 500,
    }

    try:
        logger.info(
            "[FORTUNE_GENERATOR] requesting LLM. user_id=%s date=%s model=%s",
            getattr(user, "id", None),
            fortune_date,
            settings.FORTUNE_LLM_MODEL,
        )

        llm_resp = await request_letter_llm(payload)
        content = llm_resp.get("content")
        if not content:
            raise LetterLLMError("Fortune LLM 응답에 content 없음")

        parsed = _extract_json_object(content)

        keyword = _normalize_text(parsed.get("keyword"), "부드러운 흐름")
        summary = _normalize_text(parsed.get("summary"), flow.get("message", "오늘은 흐름을 가볍게 느껴보는 게 좋아요."))

        result = {
            "love": _normalize_text(parsed.get("love"), "가까운 사람과는 차분히 호흡을 맞춰보세요."),
            "study": _normalize_text(parsed.get("study"), "한 번에 몰아서 하기보다 짧게 나눠 집중해보세요."),
            "caution": _normalize_text(parsed.get("caution"), "감정이 올라올 때는 결정을 조금 늦춰보세요."),
            "good_thing": _normalize_text(parsed.get("good_thing"), "생각보다 다정한 신호를 발견할 수 있어요."),
            "ritual": _normalize_text(parsed.get("ritual"), "잠깐 멈춰 호흡을 고르고 물 한 잔 마셔보세요."),
            "element_hint": {
                "dominant": _normalize_text(parsed.get("dominant"), dominant),
                "message": summary,
                "keyword": keyword,
                "summary": summary,
                "flow_message": flow.get("message"),
            },
            "model": llm_resp.get("model") or settings.FORTUNE_LLM_MODEL,
        }

        logger.info(
            "[FORTUNE_GENERATOR] LLM success. user_id=%s date=%s model=%s",
            getattr(user, "id", None),
            fortune_date,
            result["model"],
        )
        return result

    except (LetterLLMError, ValueError, json.JSONDecodeError) as e:
        logger.warning(
            "[FORTUNE_GENERATOR] fallback triggered. user_id=%s date=%s reason=%s",
            getattr(user, "id", None),
            fortune_date,
            str(e),
        )
        return _rule_based_fortune(flow)
