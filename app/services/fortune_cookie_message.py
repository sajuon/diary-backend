"""
포춘쿠키 쪽지 문구 생성.

LLM으로 매번 새 문구를 만들고, 실패하거나 너무 오래 걸리면 미리 써둔 문구에서 고른다.
사주 정보는 쓰지 않는다.
"""

from __future__ import annotations

import logging
import re
import secrets

from app.core.config import settings
from app.services.letter_llm_service import request_letter_llm

logger = logging.getLogger(__name__)
_rng = secrets.SystemRandom()

MESSAGE_MAX_LEN = 60

# 문구가 매번 비슷해지지 않도록 주제를 하나씩 골라 넘긴다.
THEMES = [
    "작은 행운", "뜻밖의 만남", "쉬어가기", "용기", "기다림", "새로운 시작",
    "웃음", "고마운 사람", "맛있는 것", "산책", "날씨", "잠", "꾸준함",
    "나를 아끼기", "작은 성취", "정리", "호기심", "연락", "여유", "좋은 소식",
]

FALLBACK_MESSAGES = [
    "오늘 문득 떠오른 생각이 좋은 길잡이가 될 거예요.",
    "기다리던 소식이 생각보다 가까이 있어요.",
    "천천히 가도 괜찮아요. 방향이 맞으니까요.",
    "오늘 건넨 한마디가 누군가의 하루를 바꿔요.",
    "작은 일부터 하나씩 하면 큰 일도 풀려요.",
    "오늘은 좋아하는 걸 하나 꼭 챙겨 먹어요.",
    "뜻밖의 곳에서 반가운 일이 생겨요.",
    "잠깐 쉬어가는 것도 앞으로 나아가는 방법이에요.",
    "오늘의 웃음이 내일의 운을 불러와요.",
    "미뤄둔 연락 하나가 좋은 인연을 이어줘요.",
    "생각보다 당신은 잘 해내고 있어요.",
    "오늘 정리한 작은 것 하나가 마음을 가볍게 해줘요.",
    "새로운 걸 시도하기 좋은 날이에요.",
    "조금 느려도 꾸준한 쪽이 결국 멀리 가요.",
    "오늘은 하늘을 한 번 올려다봐요. 좋은 일이 보여요.",
    "고마운 사람에게 마음을 전하면 행운이 두 배가 돼요.",
    "걱정하던 일은 생각보다 쉽게 풀려요.",
    "오늘 잠들기 전, 잘한 일 하나를 떠올려봐요.",
    "가벼운 산책이 좋은 생각을 데려와요.",
    "당신의 다정함이 곧 돌아올 거예요.",
    "오늘 마주친 작은 우연을 그냥 지나치지 마세요.",
    "지금 고민하는 일, 마음이 가는 쪽이 정답이에요.",
    "따뜻한 차 한 잔이 하루를 바꿔줄 거예요.",
    "오늘은 나를 칭찬해도 되는 날이에요.",
    "반가운 얼굴을 곧 만나게 돼요.",
    "작게 시작한 일이 큰 기쁨으로 돌아와요.",
    "오늘 하루, 조금 더 웃을 일이 생겨요.",
    "푹 자고 나면 답이 보여요.",
    "좋아하는 노래 한 곡이 기분을 바꿔줘요.",
    "당신이 기다리는 그 순간이 다가오고 있어요.",
]

SYSTEM_PROMPT = (
    "너는 포춘쿠키 속 쪽지 문구를 쓰는 작가야.\n"
    "규칙:\n"
    "- 한국어 한 문장, 공백 포함 40자 이내\n"
    "- 존댓말(~요 체), 따뜻하고 가벼운 행운의 말\n"
    "- 사주, 별자리, 타로, 띠 이야기는 하지 마\n"
    "- 불안하게 하거나 단정적으로 나쁜 일을 예언하지 마\n"
    "- 이모지, 따옴표, 번호, 설명 없이 문구만 출력해"
)


def pick_fallback_message(avoid: set[str] | None = None) -> str:
    avoid = avoid or set()
    candidates = [m for m in FALLBACK_MESSAGES if m not in avoid] or FALLBACK_MESSAGES
    return _rng.choice(candidates)


def _clean(text: str) -> str:
    text = (text or "").strip()
    if "\n" in text:
        text = next((line for line in text.splitlines() if line.strip()), "")
    text = re.sub(r"^[\-\d\.\)\s]+", "", text)
    text = text.strip().strip("\"'“”‘’「」『』").strip()
    text = re.sub(r"\s+", " ", text)
    return text


async def generate_cookie_message(recent_messages: list[str]) -> tuple[str, str]:
    """(문구, source) 반환. source는 "llm" 또는 "fallback"."""
    theme = _rng.choice(THEMES)
    avoid = "\n".join(f"- {m}" for m in recent_messages[:10])
    user_prompt = f"오늘 쪽지의 주제: {theme}\n"
    if avoid:
        user_prompt += f"최근에 쓴 문구와 겹치지 않게 써줘:\n{avoid}\n"
    user_prompt += "포춘쿠키 쪽지 문구 하나만 써줘."

    payload = {
        "model": settings.COOKIE_LLM_MODEL or settings.QUESTION_LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 1.0,
        "max_tokens": 120,
        "_request_options": {"timeout_sec": settings.COOKIE_LLM_TIMEOUT_SEC},
    }

    try:
        result = await request_letter_llm(payload)
        message = _clean(result.get("content") or "")
        if 4 <= len(message) <= MESSAGE_MAX_LEN and message not in recent_messages:
            return message, "llm"
        logger.warning("[COOKIE] unusable llm message len=%s text=%r", len(message), message[:80])
    except Exception as e:  # LLM 실패는 쿠키 열기를 막지 않는다
        logger.warning("[COOKIE] llm failed error=%s", e)

    return pick_fallback_message(set(recent_messages)), "fallback"
