# 기존 파일 경로: /home/dori/diary-backend/app/services/saju_analysis_service.py
# 수정 파일 경로: /home/dori/diary-backend/app/services/saju_analysis_service.py
# 역할: 사주 원국과 focus_points를 기반으로 오늘의 운세, 연애운, 재물운, 학업운을 type별로 다르게 생성한다.

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
from app.services.saju_chart_engine import build_saju_chart
from app.services.saju_focus_engine import build_saju_focus_points

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
DISCLAIMER_LINE = "이 내용은 오락·참고용 해석입니다."

ALLOWED_FORTUNE_TYPES = {"daily", "love", "money", "study"}

FORTUNE_TYPE_LABELS = {
    "daily": "오늘의 운세",
    "love": "오늘의 연애운",
    "money": "오늘의 재물운",
    "study": "오늘의 학업운",
}

FORTUNE_TOPICS = {
    "daily": [
        "오늘의 핵심 포인트",
        "일/공부",
        "인간관계",
        "감정 흐름",
        "연애",
        "금전",
        "컨디션",
        "실천 팁",
    ],
    "love": [
        "감정 흐름",
        "관계 거리감",
        "연락운",
        "표현 방식",
        "실천 팁",
    ],
    "money": [
        "금전 흐름",
        "소비 판단",
        "기회",
        "주의할 지출",
        "실천 팁",
    ],
    "study": [
        "집중력",
        "학업 흐름",
        "실수 포인트",
        "효율",
        "실천 팁",
    ],
}


def _normalize_fortune_type(fortune_type: Optional[str]) -> str:
    value = (fortune_type or "daily").strip().lower()
    if value not in ALLOWED_FORTUNE_TYPES:
        return "daily"
    return value


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
    weekdays = ["월", "화", "수", "목", "화", "토", "일"]
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


def _get_pillar_ganji(chart_payload: Dict[str, Any], label: str) -> str:
    pillars = chart_payload.get("pillars") or []

    for pillar in pillars:
        if pillar.get("label") == label:
            ganji = pillar.get("ganji")
            stem = pillar.get("stem")
            branch = pillar.get("branch")

            if isinstance(ganji, str) and ganji.strip():
                return ganji.strip()

            if isinstance(stem, str) and isinstance(branch, str):
                return f"{stem}{branch}"

    return ""


def _build_origin_sentence(user: User, chart_payload: Dict[str, Any]) -> str:
    name = getattr(user, "nickname", None) or "해도리 친구"

    year = _get_pillar_ganji(chart_payload, "year")
    month = _get_pillar_ganji(chart_payload, "month")
    day = _get_pillar_ganji(chart_payload, "day")
    hour = _get_pillar_ganji(chart_payload, "hour")

    if year and month and day and hour:
        return f"{name}님은 {year}년 {month}월 {day}일 {hour}시입니다."

    if year and month and day:
        return f"{name}님은 {year}년 {month}월 {day}일입니다."

    return f"{name}님의 사주 원국을 기준으로 해석합니다."


def _remove_existing_header_lines(text: str) -> str:
    cleaned = text.strip()

    cleaned = re.sub(
        r"^\s*이\s*내용은\s*오락[·ㆍ\-]?\s*참고용\s*해석입니다\.?\s*",
        "",
        cleaned,
        flags=re.MULTILINE,
    )

    cleaned = re.sub(
        r"^\s*.+?님은\s*[가-힣A-Za-z0-9]+\s*년\s*[가-힣A-Za-z0-9]+\s*월\s*[가-힣A-Za-z0-9]+\s*일(?:\s*[가-힣A-Za-z0-9]+\s*시)?입니다\.?\s*",
        "",
        cleaned,
        flags=re.MULTILINE,
    )

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _attach_fixed_header(
    user: User,
    chart_payload: Dict[str, Any],
    analysis_text: str,
) -> str:
    origin_line = _build_origin_sentence(user, chart_payload)
    body = _remove_existing_header_lines(analysis_text)

    if body:
        return f"{DISCLAIMER_LINE}\n{origin_line}\n{body}"

    return f"{DISCLAIMER_LINE}\n{origin_line}"


def _build_type_question(analysis_date: date, fortune_type: str) -> str:
    fortune_type = _normalize_fortune_type(fortune_type)
    label = FORTUNE_TYPE_LABELS.get(fortune_type, "오늘의 운세")

    common_rules = (
        f"{analysis_date.isoformat()} 기준 {label} 해석 본문을 작성해. "
        "첫 줄의 오락·참고용 문구와 사주 원국 문장은 백엔드에서 별도로 붙일 예정이므로 답변 본문에서는 반복하지 마. "
        "반드시 saju_focus_points만 근거로 사용하고, 일반 운세 문장이나 임의의 흐름을 추가하지 마. "
        "saju_focus_points의 relation.label, relation.theme, today_pillar, day_master_stem, day_master_element, "
        "today_element, dominant_element, weak_element, balance_message, core_reason, category_guides를 반영해. "
        "첫 문장은 반드시 '{이름}님 기준 {날짜}의 흐름을 보면,' 형태로 시작해. "
        "전체 흐름 요약에는 반드시 '~하는 편이 좋은 때로 읽힙니다' 형태를 포함해. "
        "차트 세부 내용이 부족하다거나 입력 정보가 부족하다는 표현은 사용하지 마. "
        "단정하지 말고 가능성 중심으로 부드럽게 설명해. "
        "마지막에는 오늘 바로 실행 가능한 행동 1~2개를 제안해. "
    )

    if fortune_type == "love":
        return (
            common_rules
            + "이번 답변은 연애운/관계운 전용이다. "
            "일, 공부, 금전, 컨디션 이야기는 직접적으로 쓰지 마. "
            "감정 흐름, 호감 표현, 연락 타이밍, 관계 거리감, 오해 가능성, 대화 방식 중심으로 작성해. "
            "솔로에게도 적용될 수 있도록 새로운 인연, 주변 사람과의 분위기, 마음을 열어도 되는 정도를 포함해. "
            "이미 관계가 있는 사람에게도 적용될 수 있도록 말투와 반응 속도에 대한 조언을 포함해. "
            "2~3문단, 6~8문장으로 작성해."
        )

    if fortune_type == "money":
        return (
            common_rules
            + "이번 답변은 재물운 전용이다. "
            "연애, 공부, 인간관계 이야기는 직접적으로 쓰지 마. "
            "소비 판단, 충동구매 주의, 돈이 새기 쉬운 지점, 작은 기회, 거래나 결제 전 확인할 부분 중심으로 작성해. "
            "과장된 금전운 표현이나 큰돈이 들어온다는 식의 단정은 금지해. "
            "오늘 돈을 어떻게 다루면 좋은지 현실적인 행동 가이드로 작성해. "
            "2~3문단, 6~8문장으로 작성해."
        )

    if fortune_type == "study":
        return (
            common_rules
            + "이번 답변은 학업운/공부운 전용이다. "
            "연애, 금전 이야기는 직접적으로 쓰지 마. "
            "집중력, 암기력, 이해력, 실수하기 쉬운 부분, 과제/시험/복습 흐름, 공부 순서 중심으로 작성해. "
            "무작정 열심히 하라는 말보다 오늘 어떤 방식으로 공부하면 효율이 좋은지 구체적으로 안내해. "
            "짧은 집중 루틴, 우선순위 정리, 복습 방식 중 하나 이상을 포함해. "
            "2~3문단, 6~8문장으로 작성해."
        )

    return (
        common_rules
        + "이번 답변은 종합운이다. "
        "오늘의 핵심 포인트, 일/공부, 인간관계, 감정 흐름, 연애, 금전, 컨디션 순서로 자연스럽게 이어서 설명해. "
        "항목명을 붙이지 말고 하나의 문단 흐름으로 작성해. "
        "category_guides의 문장을 그대로 복사하지 말고 의미만 유지해 새 문장으로 바꿔. "
        "2~3문단, 7~10문장으로 작성해."
    )


def _build_saju_payload(
    user: User,
    profile: Optional[UserBirthProfile],
    analysis_date: date,
    fortune_type: str = "daily",
) -> Dict[str, Any]:
    fortune_type = _normalize_fortune_type(fortune_type)

    chart_payload = build_saju_chart(profile)
    focus_points = build_saju_focus_points(chart_payload, analysis_date)

    payload = build_base_payload(
        mode=f"saju_{fortune_type}_analysis",
        user=user,
        birth_profile=_profile_payload(profile),
        chart=chart_payload,
        question=_build_type_question(analysis_date, fortune_type),
        topics=FORTUNE_TOPICS.get(fortune_type, FORTUNE_TOPICS["daily"]),
        tone="soft_counseling",
        length="medium",
        structure="paragraphs",
    )

    payload["user_profile"]["gender"] = str((profile.sex if profile and profile.sex else None) or "unknown")

    payload["current_context"] = {
        "as_of_date": analysis_date.isoformat(),
        "timezone": "Asia/Seoul",
        "weekday": _weekday_ko(analysis_date),
        "season": _season_hint(analysis_date),
        "app_surface": "saju_page",
        "fortune_type": fortune_type,
        "fortune_label": FORTUNE_TYPE_LABELS.get(fortune_type, "오늘의 운세"),
    }

    payload["saju_focus_points"] = focus_points

    payload["input_quality"] = {
        "birth_date_provided": bool(profile and profile.birth_date),
        "birth_time_provided": bool(profile and profile.birth_time),
        "birth_place_provided": bool(profile and profile.birth_place),
        "chart_provided": bool(chart_payload.get("chart_provided")),
    }

    payload["output_rules"] = {
        "do_not_write_disclaimer_line": True,
        "do_not_write_origin_sentence": True,
        "backend_will_attach_fixed_header": True,
        "use_only_focus_points": True,
        "fortune_type": fortune_type,
        "category_order": FORTUNE_TOPICS.get(fortune_type, FORTUNE_TOPICS["daily"]),
        "style_rules": [
            "존댓말 사용",
            "단정 표현 금지",
            "가능성 중심으로 설명",
            "운세 느낌보다 하루 행동 가이드 중심",
            "2~3문단",
            "항목명 사용 금지",
            "키워드만 나열 금지",
            "카드 type에 맞는 주제만 설명",
        ],
        "must_include": [
            "{name}님 기준 {date}의 흐름을 보면,",
            "~하는 편이 좋은 때로 읽힙니다",
        ],
        "forbidden_phrases": [
            "입력 정보는 세부 사주 세팅이 제공되었으나",
            "가능성 중심으로 가볍게 읽을 수 있습니다",
            "차트 세부 내용이 부족합니다",
            "추가 정보가 부족합니다",
            "활력",
            "새로운 시작",
            "성장",
            "에너지",
            "균형",
            "휴식",
            "과부하",
            "감정이 올라온다",
            "부드럽게 말을 건넨다",
            "과소비",
            "안정",
            "피로",
            "수면",
        ],
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


def _fallback_analysis(
    user: User,
    profile: Optional[UserBirthProfile],
    analysis_date: date,
    focus_points: Optional[Dict[str, Any]] = None,
    fortune_type: str = "daily",
) -> str:
    name = getattr(user, "nickname", None) or "해도리 친구"
    fortune_type = _normalize_fortune_type(fortune_type)
    focus_points = focus_points or {}

    relation = focus_points.get("relation") or {}
    relation_theme = relation.get("theme") or "오늘의 리듬 조절"
    direction = focus_points.get("summary") or "오늘은 해야 할 일을 작게 나누어 보는 편이 좋은 때로 읽힙니다."
    core_reason = focus_points.get("core_reason") or "오늘의 흐름은 본인의 상태를 살피며 무리하지 않는 방향이 중요해 보입니다."
    category_guides = focus_points.get("category_guides") or {}

    if fortune_type == "love":
        love = category_guides.get("love") or "연애나 가까운 관계에서는 편안한 대화의 흐름을 유지하는 쪽이 좋아 보입니다."
        relationship = category_guides.get("relationship") or "상대의 반응을 바로 단정하지 않는 편이 좋습니다."
        emotion = category_guides.get("emotion") or "감정 흐름은 짧게 기록하며 정리해보는 방식이 좋아 보입니다."

        return (
            f"{name}님 기준 {analysis_date.isoformat()}의 흐름을 보면, "
            "관계의 속도를 조금 천천히 맞추는 편이 좋은 때로 읽힙니다.\n\n"
            f"오늘의 연애운에서 핵심은 {relation_theme}입니다. {core_reason} "
            f"{emotion} {relationship} {love}\n\n"
            "오늘은 먼저 마음을 확인한 뒤 표현하는 것이 좋겠습니다. "
            "연락을 보내야 한다면 바로 길게 쓰기보다 짧고 편안한 문장으로 시작해보세요."
        )

    if fortune_type == "money":
        money = category_guides.get("money") or "금전은 선택 기준을 한 번 더 확인하는 태도가 어울립니다."

        return (
            f"{name}님 기준 {analysis_date.isoformat()}의 흐름을 보면, "
            "돈과 관련된 선택을 한 번 더 확인하는 편이 좋은 때로 읽힙니다.\n\n"
            f"오늘의 재물운에서 핵심은 {relation_theme}입니다. {core_reason} "
            f"{money} 결제나 구매는 즉흥적으로 결정하기보다 지금 필요한 지출인지 확인하는 쪽이 좋아 보입니다.\n\n"
            "오늘은 사고 싶은 것이 생기면 바로 결제하지 말고 메모장에 먼저 적어두세요. "
            "작은 금액이라도 반복되는 지출이 있는지 확인하면 돈이 새는 흐름을 줄일 수 있겠습니다."
        )

    if fortune_type == "study":
        work = category_guides.get("work_study") or "일이나 공부에서는 우선순위를 좁히는 쪽이 좋아 보입니다."
        condition = category_guides.get("condition") or "컨디션은 몸이 보내는 작은 신호를 무시하지 않는 편이 좋겠습니다."

        return (
            f"{name}님 기준 {analysis_date.isoformat()}의 흐름을 보면, "
            "공부 범위를 작게 나누어 집중하는 편이 좋은 때로 읽힙니다.\n\n"
            f"오늘의 학업운에서 핵심은 {relation_theme}입니다. {core_reason} "
            f"{work} {condition} 이해가 필요한 내용과 암기가 필요한 내용을 섞기보다 하나씩 분리해서 보는 편이 효율적입니다.\n\n"
            "오늘은 가장 어려운 부분 하나를 먼저 정하고 25분만 집중해보세요. "
            "그다음에는 틀린 부분이나 헷갈린 개념을 짧게 다시 적어두는 방식이 좋겠습니다."
        )

    work = category_guides.get("work_study") or "일이나 공부에서는 우선순위를 좁히는 쪽이 좋아 보입니다."
    relationship = category_guides.get("relationship") or "인간관계에서는 상대의 반응을 바로 단정하지 않는 편이 좋습니다."
    emotion = category_guides.get("emotion") or "감정 흐름은 짧게 기록하며 정리해보는 방식이 좋아 보입니다."
    love = category_guides.get("love") or "연애나 가까운 관계에서는 편안한 대화의 흐름을 유지하는 쪽이 좋아 보입니다."
    money = category_guides.get("money") or "금전은 선택 기준을 한 번 더 확인하는 태도가 어울립니다."
    condition = category_guides.get("condition") or "컨디션은 몸이 보내는 작은 신호를 무시하지 않는 편이 좋겠습니다."

    return (
        f"{name}님 기준 {analysis_date.isoformat()}의 흐름을 보면, "
        f"{direction}\n\n"
        f"오늘의 핵심 포인트는 {relation_theme}입니다. {core_reason} "
        f"{work} {relationship} {emotion} {love} {money} {condition}\n\n"
        "오늘은 가장 먼저 처리할 일 하나를 종이에 적고, 끝낸 뒤에는 남은 일을 다시 세 가지 안으로 줄여보세요. "
        "대화가 필요한 일이 있다면 바로 보내기보다 한 번 읽어본 뒤 전달하는 편이 좋겠습니다."
    )


async def generate_saju_analysis(
    user: User,
    profile: Optional[UserBirthProfile],
    *,
    analysis_date: Optional[date] = None,
    fortune_type: str = "daily",
) -> Dict[str, Any]:
    target_date = analysis_date or datetime.now(KST).date()
    fortune_type = _normalize_fortune_type(fortune_type)

    request_object = _build_saju_payload(user, profile, target_date, fortune_type)
    chart_payload = request_object.get("chart") or {}
    focus_points = request_object.get("saju_focus_points") or {}

    payload = {
        "model": settings.SAJU_LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(
                    request_object,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        "temperature": 0.45,
        "max_tokens": 900,
        "_request_options": {
            "timeout_sec": 90,
            "strategy_allowlist": [
                "openwebui-openai",
                "explicit-openwebui-openai",
            ],
        },
    }

    try:
        logger.info(
            "[SAJU_ANALYSIS] requesting LLM. user_id=%s date=%s type=%s model=%s chart_provided=%s",
            getattr(user, "id", None),
            target_date,
            fortune_type,
            settings.SAJU_LLM_MODEL,
            bool(chart_payload.get("chart_provided")),
        )

        llm_resp = await request_letter_llm(payload)
        content = llm_resp.get("content")

        if not isinstance(content, str) or not content.strip():
            raise LetterLLMError("Saju LLM 응답에 content 없음")

        cleaned = _clean_analysis_text(content)

        if not cleaned:
            raise LetterLLMError("Saju LLM 응답 정리 후 빈 문자열")

        final_analysis = _attach_fixed_header(user, chart_payload, cleaned)

        logger.info(
            "[SAJU_ANALYSIS] LLM success. user_id=%s date=%s type=%s model=%s",
            getattr(user, "id", None),
            target_date,
            fortune_type,
            llm_resp.get("model") or settings.SAJU_LLM_MODEL,
        )

        return {
            "analysis": final_analysis,
            "analysis_date": target_date.isoformat(),
            "model": llm_resp.get("model") or settings.SAJU_LLM_MODEL,
            "chart_provided": bool(chart_payload.get("chart_provided")),
            "pillars": chart_payload.get("pillars", []),
            "elementSummary": chart_payload.get("elementSummary", {}),
            "saju_focus_points": focus_points,
            "fortune_type": fortune_type,
        }

    except LetterLLMError as exc:
        logger.warning(
            "[SAJU_ANALYSIS] fallback triggered. user_id=%s date=%s type=%s reason=%s",
            getattr(user, "id", None),
            target_date,
            fortune_type,
            str(exc),
        )

        fallback_text = _fallback_analysis(
            user=user,
            profile=profile,
            analysis_date=target_date,
            focus_points=focus_points,
            fortune_type=fortune_type,
        )
        final_analysis = _attach_fixed_header(user, chart_payload, fallback_text)

        return {
            "analysis": final_analysis,
            "analysis_date": target_date.isoformat(),
            "model": f"rule-based-saju-{fortune_type}-fallback",
            "chart_provided": bool(chart_payload.get("chart_provided")),
            "pillars": chart_payload.get("pillars", []),
            "elementSummary": chart_payload.get("elementSummary", {}),
            "saju_focus_points": focus_points,
            "fortune_type": fortune_type,
        }