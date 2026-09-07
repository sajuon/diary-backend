# /home/dori/diary-backend/app/services/letter_llm_service.py
from __future__ import annotations

from typing import Any, Dict, Optional
import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LetterLLMError(Exception):
    pass


# ---------------------------------------------------------------------------
# reasoning(<think>) 블록 제거
# ---------------------------------------------------------------------------

_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think\b[^>]*>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"</think\s*>", re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """
    모델이 응답 본문에 함께 내보내는 사고과정(<think>...</think>)을 제거한다.
    - 정상적으로 열고 닫힌 블록 제거
    - 여는 태그 없이 </think>로만 끝나는 경우: 그 앞은 전부 사고과정으로 간주하고 버림
    - 닫히지 않은 <think>가 남은 경우(토큰 잘림): 그 뒤를 통째로 버림
    """
    if not text:
        return ""

    # 1) 정상 블록 제거
    text = _THINK_BLOCK_RE.sub("", text)

    # 2) 여는 태그 없이 닫는 태그만 남은 경우 → 마지막 </think> 이후만 본문
    close_matches = list(_THINK_CLOSE_RE.finditer(text))
    if close_matches:
        text = text[close_matches[-1].end():]

    # 3) 닫히지 않은 <think>가 남은 경우 → 그 앞까지만 본문
    open_match = _THINK_OPEN_RE.search(text)
    if open_match:
        text = text[: open_match.start()]

    return text.strip()


# ---------------------------------------------------------------------------
# LUDO Assistant API 클라이언트
# ---------------------------------------------------------------------------


def _chat_completions_url() -> str:
    base = (settings.LLM_BASE_URL or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = (getattr(settings, "LLM_API_KEY", None) or "").strip()
    if not api_key:
        raise LetterLLMError("LLM_API_KEY가 설정되어 있지 않습니다 (.env 확인).")
    headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _timeout(total_override: Optional[float] = None) -> httpx.Timeout:
    configured = total_override
    if configured is None:
        configured = getattr(settings, "LLM_TIMEOUT_SEC", 180)
    total = max(5.0, float(configured))
    connect_timeout = min(3.0, total)
    return httpx.Timeout(
        total,
        connect=connect_timeout,
        read=total,
        write=min(10.0, total),
        pool=connect_timeout,
    )


async def request_letter_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    LUDO Assistant API (OpenAI-compatible) endpoint:
      POST {LLM_BASE_URL}/chat/completions
    LLM_BASE_URL 예: http://172.30.1.59:18791/v1
    """
    request_payload = dict(payload)
    request_options = request_payload.pop("_request_options", None) or {}

    if not isinstance(request_options, dict):
        raise LetterLLMError("payload._request_options는 dict여야 합니다.")

    timeout_override_raw = request_options.get("timeout_sec")
    timeout_override: Optional[float] = None
    if timeout_override_raw is not None:
        try:
            timeout_override = float(timeout_override_raw)
        except (TypeError, ValueError) as exc:
            raise LetterLLMError("payload._request_options.timeout_sec가 올바르지 않습니다.") from exc

    if "model" not in request_payload or not request_payload.get("model"):
        request_payload["model"] = getattr(settings, "LLM_MODEL", None) or "dori-diary-deploy"

    if "messages" not in request_payload or not isinstance(request_payload["messages"], list):
        raise LetterLLMError("payload.messages가 없습니다. OpenAI 형식(messages 리스트)으로 보내야 합니다.")

    request_payload.setdefault("stream", False)

    url = _chat_completions_url()
    headers = _headers()
    model_name = request_payload.get("model")

    logger.info("[LETTER_LLM] request start url=%s model=%s", url, model_name)

    try:
        async with httpx.AsyncClient(timeout=_timeout(timeout_override)) as client:
            response = await client.post(url, headers=headers, json=request_payload)
    except httpx.RequestError as e:
        logger.exception("[LETTER_LLM] request error error=%s", str(e))
        raise LetterLLMError(f"LUDO API 요청 실패: {e}") from e

    logger.info(
        "[LETTER_LLM] response received status=%s model=%s",
        response.status_code,
        model_name,
    )

    if response.status_code >= 400:
        body = response.text[:500]
        logger.warning("[LETTER_LLM] http error status=%s body=%s", response.status_code, body)
        raise LetterLLMError(f"LUDO API HTTP 오류: {response.status_code} / {body}")

    try:
        data = response.json()
    except Exception as e:
        logger.exception("[LETTER_LLM] json parse failed body=%s", response.text[:500])
        raise LetterLLMError(f"LUDO API 응답 JSON 파싱 실패: {e}") from e

    try:
        raw_content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        logger.exception("[LETTER_LLM] response shape invalid data=%s", str(data)[:500])
        raise LetterLLMError(f"LUDO API 응답 형식 오류: {e} / data={str(data)[:300]}") from e

    if not isinstance(raw_content, str) or not raw_content.strip():
        raise LetterLLMError("LUDO API 응답 content가 비어있습니다.")

    content = strip_reasoning(raw_content)

    if not content:
        logger.warning(
            "[LETTER_LLM] content empty after strip_reasoning model=%s raw_len=%d raw_head=%s",
            model_name,
            len(raw_content),
            raw_content[:300],
        )
        raise LetterLLMError(
            "사고과정 제거 후 본문이 비어있습니다 (max_tokens 부족으로 본문이 생성되지 않았을 가능성)."
        )

    if len(content) != len(raw_content.strip()):
        logger.info(
            "[LETTER_LLM] reasoning stripped model=%s raw_len=%d clean_len=%d",
            model_name,
            len(raw_content),
            len(content),
        )

    return {
        "content": content,
        "model": data.get("model") or model_name,
        "raw": data,
    }