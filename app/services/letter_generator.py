from __future__ import annotations

from typing import Dict, Optional, Any
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune

from app.services.letter_llm_service import request_letter_llm, LetterLLMError


def kst_now_date_str() -> str:
    d = datetime.now(ZoneInfo("Asia/Seoul"))
    return f"{d.year}. {d.month}. {d.day}."


def build_system_prompt() -> str:
    # ✅ 해도리 편지 톤/형식 강제
    return (
        "너는 '해도리'라는 귀여운 해달 캐릭터다.\n"
        "사용자의 일기를 읽고, 짧은 편지 형태의 피드백을 작성한다.\n"
        "\n"
        "[반드시 지킬 형식]\n"
        "To. {닉네임}님\n"
        "본문: 3~6문장, 한 문단(줄바꿈 최소), 따뜻하지만 과장/감정상담 톤 금지, 훈계 금지\n"
        "오늘 사용자가 해낸 점을 1개 구체적으로 짚고, 아주 작은 행동 1개만 제안\n"
        "날짜: YYYY. M. D.\n"
        "from. 해도리\n"
        "\n"
        "[금지]\n"
        "- 음주 권유\n"
        "- 여러 문단/과한 줄바꿈\n"
        "- 형식 누락\n"
        "- from을 다른 이름으로 쓰기\n"
    )


def build_user_prompt(
    user: User,
    diary_entry: DiaryEntry,
    fortune: Optional[DailyFortune],
) -> str:
    fortune_hint = ""
    # fortune에 element_hint 같은게 있으면 “살짝 힌트”만
    if fortune and getattr(fortune, "element_hint", None):
        fortune_hint = f"\n\n(참고 힌트: {fortune.element_hint})"

    return (
        f"닉네임: {getattr(user, 'nickname', None) or '사용자'}\n"
        f"일기:\n{diary_entry.content}"
        f"{fortune_hint}\n\n"
        "위 내용을 바탕으로, 해도리 편지를 작성해줘."
    )


def build_llm_payload(
    user: User,
    diary_entry: DiaryEntry,
    fortune: Optional[DailyFortune],
) -> Dict[str, Any]:
    system_text = build_system_prompt()
    user_text = build_user_prompt(user, diary_entry, fortune)

    return {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.7,
        "max_tokens": 550,
    }


def rule_based_letter(nickname: str) -> str:
    # ✅ fallback도 "편지 포맷" 맞춰주기
    date_str = kst_now_date_str()
    return (
        f"To. {nickname}님\n"
        "오늘은 지쳤는데도 끝까지 해냈다는 말이 정말 크게 들려.\n"
        "마음이 무거운 날엔 ‘완벽’보다 ‘완료’가 더 값진 거 알지?\n"
        "지금은 딱 30초만 어깨 힘 풀고 숨 한 번 길게 내쉬어보자.\n"
        "오늘의 너는 이미 충분히 잘했어.\n"
        f"{date_str}\n"
        "from. 해도리"
    )


async def generate_otter_letter(
    user: User,
    diary_entry: DiaryEntry,
    fortune: Optional[DailyFortune],
) -> Dict[str, Any]:
    """
    반환:
    {
      "content": "...",
      "element_hint": {...} | None,
      "model": "..."
    }
    """
    element_hint = None
    if fortune and getattr(fortune, "element_hint", None):
        element_hint = fortune.element_hint

    payload = build_llm_payload(user, diary_entry, fortune)

    nickname = getattr(user, "nickname", None) or "사용자"

    try:
        llm_resp = await request_letter_llm(payload)

        content = llm_resp.get("content")
        if not content:
            raise LetterLLMError("LLM 응답에 content 없음")

        return {
            "content": content,
            "element_hint": element_hint,
            "model": llm_resp.get("model") or settings.LLM_MODEL,
        }

    except LetterLLMError:
        return {
            "content": rule_based_letter(nickname),
            "element_hint": element_hint,
            "model": "rule-based-letter-fallback",
        }