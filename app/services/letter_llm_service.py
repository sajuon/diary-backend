from __future__ import annotations

from typing import Any, Dict
import httpx

from app.core.config import settings
print("LLM_API_KEY head:", (settings.LLM_API_KEY or "")[:10])

class LetterLLMError(Exception):
    pass


def _debug_log():
    # import 시점마다 출력되면 reload에서 너무 많이 찍혀서 DEBUG일 때만
    if getattr(settings, "DEBUG", False):
        print("LLM_BASE_URL:", settings.LLM_BASE_URL)
        print("LLM_MODEL:", getattr(settings, "LLM_MODEL", None))
        print("LLM_API_KEY loaded:", bool(getattr(settings, "LLM_API_KEY", "")))


_debug_log()


async def request_letter_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Open WebUI (OpenAI-compatible) endpoint:
      POST {LLM_BASE_URL}/api/chat/completions

    payload example:
    {
      "model": "dori-text-v6",
      "messages": [
        {"role":"system","content":"..."},
        {"role":"user","content":"..."}
      ],
      "temperature": 0.7,
      "max_tokens": 550
    }

    return:
    {
      "content": "...",
      "model": "...",
      "raw": {...}
    }
    """
    base = settings.LLM_BASE_URL.rstrip("/")
    url = f"{base}/api/chat/completions"

    api_key = getattr(settings, "LLM_API_KEY", None)
    if not api_key:
        raise LetterLLMError("LLM_API_KEY가 비어있습니다. .env / settings 로딩을 확인하세요.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(
        settings.LLM_TIMEOUT_SEC,
        connect=min(10, settings.LLM_TIMEOUT_SEC),
        read=settings.LLM_TIMEOUT_SEC,
        write=min(10, settings.LLM_TIMEOUT_SEC),
        pool=min(10, settings.LLM_TIMEOUT_SEC),
    )

    # OpenAI compatible 최소 필드 검증
    if "model" not in payload:
        payload["model"] = getattr(settings, "LLM_MODEL", None) or "dori-text-v6"
    if "messages" not in payload or not isinstance(payload["messages"], list):
        raise LetterLLMError("payload.messages가 없습니다. OpenAI 형식(messages 리스트)으로 보내야 합니다.")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as e:
        raise LetterLLMError(f"LLM 요청 실패(RequestError): {e}") from e

    # 인증/권한 문제
    if resp.status_code == 401:
        raise LetterLLMError(
            f"401 Unauthorized: LLM_API_KEY가 유효한지 / Bearer 헤더가 맞는지 확인. body={resp.text[:200]}"
        )
    if resp.status_code == 403:
        raise LetterLLMError(
            f"403 Forbidden: 키 권한 문제이거나 모델 접근 제한. body={resp.text[:200]}"
        )

    if resp.status_code >= 400:
        raise LetterLLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
    except Exception as e:
        raise LetterLLMError(f"LLM JSON 파싱 실패: {e} / body={resp.text[:300]}") from e

    # OpenAI response parsing
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        raise LetterLLMError(f"응답 형태가 예상과 다름: {str(data)[:300]}")

    return {
        "content": content,
        "model": data.get("model") or payload.get("model") or getattr(settings, "LLM_MODEL", None),
        "raw": data,
    }