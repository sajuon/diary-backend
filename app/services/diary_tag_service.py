from __future__ import annotations

import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SummaryTagError(Exception):
    pass


def normalize_tag(text: str) -> str:
    if not text:
        return "#하루기록"

    text = text.strip()
    text = text.replace('"', "").replace("'", "")
    text = text.replace("“", "").replace("”", "")
    text = text.replace("‘", "").replace("’", "")

    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    if "\n" in text:
        text = text.splitlines()[0].strip()

    text = text.split(",")[0].strip()
    text = text.split(" - ")[0].strip()
    text = text.split(":")[0].strip()

    text = re.sub(r"[.!?。！]+$", "", text)
    text = re.sub(r"\s+", "", text)

    if text and not text.startswith("#"):
        text = f"#{text}"

    text = re.sub(r"[^#0-9A-Za-z가-힣_]", "", text)

    if text in {"", "#"}:
        return "#하루기록"

    if len(text) > 20:
        text = text[:20]

    return text


def fallback_summary_tag(content: str) -> str:
    text = (content or "").strip()

    if not text:
        return "#하루기록"

    if any(word in text for word in ["기쁘", "행복", "좋았", "신났", "뿌듯", "설렜"]):
        return "#기분좋은하루"

    if any(word in text for word in ["힘들", "지쳤", "피곤", "우울", "속상", "답답"]):
        return "#지친하루"

    if any(word in text for word in ["공부", "시험", "과제", "수업", "발표"]):
        return "#공부한하루"

    if any(word in text for word in ["친구", "가족", "엄마", "아빠", "언니", "동생", "사람"]):
        return "#함께한하루"

    if any(word in text for word in ["걱정", "불안", "고민", "스트레스"]):
        return "#생각많은하루"

    return "#하루기록"


def build_summary_tag_prompt(content: str) -> str:
    return f"""
다음 일기를 먼저 짧게 이해한 뒤,
그날의 핵심 감정이나 주제를 가장 잘 나타내는 한국어 해시태그 1개만 출력해줘.

규칙:
- 반드시 해시태그 1개만 출력
- 설명, 이유, 문장, 따옴표, 부가 텍스트 절대 금지
- 예시: #벚꽃기대 #개발집중 #피곤한하루 #미래고민
- 너무 일반적인 #일기 #하루 같은 표현은 가능하면 피하기
- 공백 없이 짧게 작성
- 한국어 해시태그로 작성
- 출력은 오직 태그 한 개만

일기 내용:
{content}
""".strip()


def _chat_completions_url() -> str:
    base = settings.LLM_BASE_URL.rstrip("/")
    return f"{base}/api/chat/completions"


def _headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
    }

    api_key = (settings.LLM_API_KEY or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return headers


async def call_summary_tag_llm(content: str) -> tuple[str, str]:
    model_name = getattr(settings, "SUMMARY_LLM_MODEL", None) or settings.LLM_MODEL

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "너는 일기의 핵심 감정과 주제를 파악해서 "
                    "짧은 한국어 해시태그 1개만 출력하는 도우미야."
                ),
            },
            {
                "role": "user",
                "content": build_summary_tag_prompt(content),
            },
        ],
        "temperature": 0.4,
        "max_tokens": 30,
    }

    url = _chat_completions_url()
    headers = _headers()

    logger.info(
        "[SUMMARY_TAG] request start url=%s model=%s content_len=%s preview=%s",
        url,
        model_name,
        len(content or ""),
        (content or "")[:120].replace("\n", " "),
    )

    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SEC) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )
    except httpx.RequestError as e:
        logger.exception("[SUMMARY_TAG] request error error=%s", str(e))
        raise SummaryTagError(f"태그 LLM 요청 실패: {str(e)}") from e

    logger.info(
        "[SUMMARY_TAG] response received status=%s model=%s",
        response.status_code,
        model_name,
    )

    if response.status_code >= 400:
        logger.error(
            "[SUMMARY_TAG] http error status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise SummaryTagError(
            f"태그 LLM HTTP 오류: {response.status_code} / {response.text[:300]}"
        )

    try:
        data = response.json()
    except Exception as e:
        logger.exception("[SUMMARY_TAG] json parse failed body=%s", response.text[:500])
        raise SummaryTagError(f"태그 응답 JSON 파싱 실패: {str(e)}") from e

    try:
        raw_tag = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
    except Exception as e:
        logger.exception("[SUMMARY_TAG] response shape invalid data=%s", str(data)[:500])
        raise SummaryTagError(f"태그 응답 형식 오류: {str(e)}") from e

    summary_tag = normalize_tag(raw_tag)

    logger.info(
        "[SUMMARY_TAG] response parsed raw=%s normalized=%s",
        repr(raw_tag),
        summary_tag,
    )

    if not summary_tag or summary_tag == "#":
        raise SummaryTagError("태그 생성 결과가 비어 있습니다.")

    return summary_tag, model_name


async def generate_summary_tag(content: str) -> str:
    text = (content or "").strip()

    if not text:
        logger.warning("[SUMMARY_TAG] empty content -> fallback")
        return "#하루기록"

    try:
        summary_tag, _ = await call_summary_tag_llm(text)
        return summary_tag
    except Exception as e:
        fallback_tag = fallback_summary_tag(text)
        logger.exception(
            "[SUMMARY_TAG] failed, using fallback error=%s fallback=%s",
            str(e),
            fallback_tag,
        )
        return fallback_tag