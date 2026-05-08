# /home/dori/diary-backend/app/services/letter_llm_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LetterLLMError(Exception):
    pass


@dataclass(frozen=True)
class EndpointStrategy:
    name: str
    url: str
    root: str
    request_kind: str
    use_auth: bool
    model_paths: tuple[str, ...]


_cached_strategy: Optional[EndpointStrategy] = None
_cached_models: dict[str, str] = {}


def _debug_log() -> None:
    if getattr(settings, "DEBUG", False):
        logger.info("[LETTER_LLM] LLM_BASE_URL=%s", settings.LLM_BASE_URL)
        logger.info("[LETTER_LLM] LLM_MODEL=%s", getattr(settings, "LLM_MODEL", None))
        logger.info(
            "[LETTER_LLM] LLM_PROVIDER=%s",
            getattr(settings, "LLM_PROVIDER", "auto"),
        )
        logger.info(
            "[LETTER_LLM] LLM_API_KEY loaded=%s",
            bool(getattr(settings, "LLM_API_KEY", "")),
        )
        logger.info(
            "[LETTER_LLM] LLM_API_KEY head=%s",
            (getattr(settings, "LLM_API_KEY", "") or "")[:10],
        )


_debug_log()


def _normalize_url(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for item in items:
        normalized = _normalize_url(item)
        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        result.append(normalized)

    return result


def _configured_base_urls() -> list[str]:
    """
    LLM 요청 주소 후보를 만든다.

    중요:
    - 기본 local/ollama 후보를 자동으로 넣지 않는다.
    - .env의 LLM_BASE_URL을 최우선이자 기본값으로 사용한다.
    - 추가 후보가 필요할 때만 LLM_FALLBACK_BASE_URLS에 직접 적는다.

    예:
    LLM_BASE_URL=http://172.30.1.77:8080
    LLM_FALLBACK_BASE_URLS=http://127.0.0.1:8080,http://localhost:8080
    """
    urls: list[str] = []

    primary = _normalize_url(getattr(settings, "LLM_BASE_URL", ""))
    if primary:
        urls.append(primary)

    extra = getattr(settings, "LLM_FALLBACK_BASE_URLS", "") or ""
    if extra:
        urls.extend(_normalize_url(item) for item in extra.split(",") if item.strip())

    return _dedupe(urls)


def _strategies_for_root(root: str) -> list[EndpointStrategy]:
    provider = (getattr(settings, "LLM_PROVIDER", "auto") or "auto").strip().lower()

    openwebui_strategies = [
        EndpointStrategy(
            name="openwebui-openai",
            url=f"{root}/api/chat/completions",
            root=root,
            request_kind="openai_chat",
            use_auth=True,
            model_paths=("/api/models", "/ollama/api/tags", "/api/tags"),
        ),
        EndpointStrategy(
            name="openwebui-ollama-chat",
            url=f"{root}/ollama/api/chat",
            root=root,
            request_kind="ollama_chat",
            use_auth=True,
            model_paths=("/ollama/api/tags", "/api/models", "/api/tags"),
        ),
        EndpointStrategy(
            name="openwebui-ollama-generate",
            url=f"{root}/ollama/api/generate",
            root=root,
            request_kind="ollama_generate",
            use_auth=True,
            model_paths=("/ollama/api/tags", "/api/models", "/api/tags"),
        ),
    ]

    ollama_strategies = [
        EndpointStrategy(
            name="ollama-chat",
            url=f"{root}/api/chat",
            root=root,
            request_kind="ollama_chat",
            use_auth=False,
            model_paths=("/api/tags",),
        ),
        EndpointStrategy(
            name="ollama-generate",
            url=f"{root}/api/generate",
            root=root,
            request_kind="ollama_generate",
            use_auth=False,
            model_paths=("/api/tags",),
        ),
    ]

    if provider == "openwebui":
        return openwebui_strategies + ollama_strategies

    if provider == "ollama":
        return ollama_strategies + openwebui_strategies

    return [
        openwebui_strategies[0],
        openwebui_strategies[1],
        ollama_strategies[0],
        openwebui_strategies[2],
        ollama_strategies[1],
    ]


def _strategy_from_explicit_url(url: str) -> Optional[EndpointStrategy]:
    known_suffixes = [
        (
            "/api/chat/completions",
            "openai_chat",
            True,
            "explicit-openwebui-openai",
            ("/api/models", "/ollama/api/tags", "/api/tags"),
        ),
        (
            "/ollama/api/chat",
            "ollama_chat",
            True,
            "explicit-openwebui-ollama-chat",
            ("/ollama/api/tags", "/api/models", "/api/tags"),
        ),
        (
            "/ollama/api/generate",
            "ollama_generate",
            True,
            "explicit-openwebui-ollama-generate",
            ("/ollama/api/tags", "/api/models", "/api/tags"),
        ),
        (
            "/api/chat",
            "ollama_chat",
            False,
            "explicit-ollama-chat",
            ("/api/tags",),
        ),
        (
            "/api/generate",
            "ollama_generate",
            False,
            "explicit-ollama-generate",
            ("/api/tags",),
        ),
    ]

    normalized = _normalize_url(url)

    for suffix, kind, use_auth, name, model_paths in known_suffixes:
        if normalized.endswith(suffix):
            root = normalized[: -len(suffix)].rstrip("/")
            return EndpointStrategy(
                name=name,
                url=normalized,
                root=root,
                request_kind=kind,
                use_auth=use_auth,
                model_paths=model_paths,
            )

    return None


def _is_strategy_allowed_for_current_base(strategy: EndpointStrategy) -> bool:
    configured_roots = set(_configured_base_urls())

    if strategy.root in configured_roots:
        return True

    return any(strategy.url.startswith(root + "/") for root in configured_roots)


def _candidate_strategies() -> list[EndpointStrategy]:
    strategies: list[EndpointStrategy] = []

    for configured in _configured_base_urls():
        explicit = _strategy_from_explicit_url(configured)
        if explicit is not None:
            strategies.append(explicit)
            continue

        strategies.extend(_strategies_for_root(configured))

    if _cached_strategy is not None and _is_strategy_allowed_for_current_base(_cached_strategy):
        strategies.insert(0, _cached_strategy)

    deduped: list[EndpointStrategy] = []
    seen: set[tuple[str, str]] = set()

    for strategy in strategies:
        key = (strategy.request_kind, strategy.url)
        if key in seen:
            continue

        seen.add(key)
        deduped.append(strategy)

    return deduped


def _headers(use_auth: bool) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = (getattr(settings, "LLM_API_KEY", None) or "").strip()

    if use_auth and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return headers


def _timeout(total_override: Optional[float] = None) -> httpx.Timeout:
    configured = total_override

    if configured is None:
        configured = getattr(settings, "LLM_TIMEOUT_SEC", 60)

    total = max(5.0, float(configured))
    connect_timeout = min(3.0, float(total))
    write_timeout = min(10.0, float(total))

    return httpx.Timeout(
        total,
        connect=connect_timeout,
        read=total,
        write=write_timeout,
        pool=connect_timeout,
    )


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []

        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)

        return "\n".join(parts)

    return ""


def _messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []

    for message in messages:
        role = str(message.get("role", "user")).upper()
        content = _extract_text_content(message.get("content"))

        if content:
            lines.append(f"{role}:\n{content}")

    lines.append("ASSISTANT:\n")
    return "\n\n".join(lines)


def _prepare_request_payload(
    original_payload: Dict[str, Any],
    strategy: EndpointStrategy,
    model: str,
) -> Dict[str, Any]:
    if strategy.request_kind == "openai_chat":
        request_payload = dict(original_payload)
        request_payload["model"] = model
        return request_payload

    options: dict[str, Any] = {}

    if original_payload.get("temperature") is not None:
        options["temperature"] = original_payload["temperature"]

    if original_payload.get("max_tokens") is not None:
        options["num_predict"] = original_payload["max_tokens"]

    messages = original_payload.get("messages") or []

    if strategy.request_kind == "ollama_chat":
        request_payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        if options:
            request_payload["options"] = options

        return request_payload

    request_payload = {
        "model": model,
        "prompt": _messages_to_prompt(messages),
        "stream": False,
    }

    if options:
        request_payload["options"] = options

    return request_payload


def _parse_response_payload(
    strategy: EndpointStrategy,
    payload: Dict[str, Any],
    fallback_model: str,
) -> tuple[str, str]:
    if strategy.request_kind == "openai_chat":
        content = payload["choices"][0]["message"]["content"]

        if not isinstance(content, str) or not content.strip():
            raise LetterLLMError("LLM 응답 content가 비어있습니다.")

        return content, str(fallback_model or payload.get("model") or "")

    if strategy.request_kind == "ollama_chat":
        message = payload.get("message")

        if isinstance(message, dict):
            content = message.get("content")

            if isinstance(content, str) and content.strip():
                return content, str(payload.get("model") or fallback_model)

    content = payload.get("response")

    if isinstance(content, str) and content.strip():
        return content, str(payload.get("model") or fallback_model)

    raise LetterLLMError(f"응답 형태가 예상과 다름: {str(payload)[:300]}")


def _extract_model_ids(payload: Any) -> list[str]:
    rows: list[Any] = []

    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            rows = payload["data"]
        elif isinstance(payload.get("models"), list):
            rows = payload["models"]
        elif isinstance(payload.get("items"), list):
            rows = payload["items"]
    elif isinstance(payload, list):
        rows = payload

    models: list[str] = []

    for row in rows:
        if isinstance(row, str) and row.strip():
            models.append(row.strip())
            continue

        if not isinstance(row, dict):
            continue

        for key in ("id", "model", "name"):
            value = row.get(key)

            if isinstance(value, str) and value.strip():
                models.append(value.strip())
                break

    return _dedupe(models)


async def _fetch_models(
    client: httpx.AsyncClient,
    strategy: EndpointStrategy,
) -> list[str]:
    for model_path in strategy.model_paths:
        model_url = f"{strategy.root}{model_path}" if strategy.root else model_path

        try:
            response = await client.get(model_url, headers=_headers(strategy.use_auth))
        except httpx.RequestError:
            continue

        if response.status_code >= 400:
            continue

        try:
            payload = response.json()
        except Exception:
            continue

        models = _extract_model_ids(payload)

        if models:
            return models

    return []


def _resolve_model_name(requested_model: str, available_models: list[str]) -> str:
    if not available_models:
        return requested_model

    requested = (requested_model or "").strip()

    if not requested:
        return available_models[0]

    requested_lower = requested.lower()
    exact = {model.lower(): model for model in available_models}

    if requested_lower in exact:
        return exact[requested_lower]

    requested_base = requested_lower.split(":", 1)[0]
    requested_tail = requested_lower.rsplit("/", 1)[-1]

    for model in available_models:
        candidate = model.lower()

        if candidate.endswith(requested_lower) or requested_lower in candidate:
            return model

    for model in available_models:
        candidate = model.lower()
        candidate_base = candidate.split(":", 1)[0]
        candidate_tail = candidate.rsplit("/", 1)[-1]

        if candidate_base == requested_base or candidate_tail == requested_tail:
            return model

    return available_models[0]


def _looks_like_model_not_found(status_code: int, body: str) -> bool:
    text = body.lower()

    if status_code not in (400, 404):
        return False

    if "model" not in text:
        return False

    return any(
        phrase in text
        for phrase in (
            "not found",
            "does not exist",
            "no such model",
            "unknown model",
            "missing model",
        )
    )


async def request_letter_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    OpenWebUI/OpenAI-compatible endpoint:
      POST {LLM_BASE_URL}/api/chat/completions
    """
    global _cached_strategy

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

    strategy_allowlist = {
        str(name).strip()
        for name in (request_options.get("strategy_allowlist") or [])
        if str(name).strip()
    }

    if "model" not in request_payload or not request_payload.get("model"):
        request_payload["model"] = getattr(settings, "LLM_MODEL", None) or "dori-text-v6"

    if "messages" not in request_payload or not isinstance(request_payload["messages"], list):
        raise LetterLLMError("payload.messages가 없습니다. OpenAI 형식(messages 리스트)으로 보내야 합니다.")

    requested_model = str(request_payload.get("model") or "").strip()
    errors: list[str] = []

    candidate_strategies = _candidate_strategies()

    if strategy_allowlist:
        candidate_strategies = [
            strategy for strategy in candidate_strategies if strategy.name in strategy_allowlist
        ]

    if not candidate_strategies:
        raise LetterLLMError("사용 가능한 LLM 전략이 없습니다.")

    async with httpx.AsyncClient(timeout=_timeout(timeout_override)) as client:
        for strategy in candidate_strategies:
            cached_model = _cached_models.get(strategy.url)
            model_to_use = requested_model or cached_model

            logger.info(
                "[LETTER_LLM] trying strategy=%s url=%s model=%s",
                strategy.name,
                strategy.url,
                model_to_use,
            )

            if not model_to_use:
                available = await _fetch_models(client, strategy)
                model_to_use = _resolve_model_name(requested_model, available)

            outgoing_payload = _prepare_request_payload(
                request_payload,
                strategy,
                model_to_use,
            )

            try:
                response = await client.post(
                    strategy.url,
                    headers=_headers(strategy.use_auth),
                    json=outgoing_payload,
                )
            except httpx.RequestError as e:
                logger.warning(
                    "[LETTER_LLM] request error. strategy=%s url=%s error=%s",
                    strategy.name,
                    strategy.url,
                    str(e),
                )
                errors.append(f"{strategy.name}: {e}")
                continue

            logger.info(
                "[LETTER_LLM] response received. strategy=%s status=%s model=%s",
                strategy.name,
                response.status_code,
                model_to_use,
            )

            if response.status_code in (401, 403):
                logger.warning(
                    "[LETTER_LLM] auth error. strategy=%s status=%s body=%s",
                    strategy.name,
                    response.status_code,
                    response.text[:300],
                )
                errors.append(f"{strategy.name}: HTTP {response.status_code}")
                continue

            if response.status_code >= 400:
                body = response.text[:500]
                logger.warning(
                    "[LETTER_LLM] http error. strategy=%s status=%s body=%s",
                    strategy.name,
                    response.status_code,
                    body,
                )

                if _looks_like_model_not_found(response.status_code, body):
                    available_models = await _fetch_models(client, strategy)
                    resolved_model = _resolve_model_name(
                        requested_model,
                        available_models,
                    )

                    if resolved_model and resolved_model != model_to_use:
                        logger.info(
                            "[LETTER_LLM] retrying with discovered model. strategy=%s requested=%s resolved=%s",
                            strategy.name,
                            requested_model,
                            resolved_model,
                        )

                        retry_payload = _prepare_request_payload(
                            request_payload,
                            strategy,
                            resolved_model,
                        )

                        try:
                            retry_response = await client.post(
                                strategy.url,
                                headers=_headers(strategy.use_auth),
                                json=retry_payload,
                            )
                        except httpx.RequestError as e:
                            errors.append(f"{strategy.name}: retry failed ({e})")
                            continue

                        if retry_response.status_code < 400:
                            try:
                                data = retry_response.json()
                            except Exception as e:
                                raise LetterLLMError(
                                    f"LLM JSON 파싱 실패: {e} / body={retry_response.text[:300]}"
                                ) from e

                            content, resolved = _parse_response_payload(
                                strategy,
                                data,
                                resolved_model,
                            )

                            _cached_strategy = strategy
                            _cached_models[strategy.url] = resolved

                            logger.info(
                                "[LETTER_LLM] success after model discovery. strategy=%s model=%s content_len=%s",
                                strategy.name,
                                resolved,
                                len(content),
                            )

                            return {
                                "content": content,
                                "model": resolved,
                                "raw": data,
                            }

                        errors.append(
                            f"{strategy.name}: HTTP {retry_response.status_code} after model retry"
                        )
                        continue

                errors.append(f"{strategy.name}: HTTP {response.status_code}")
                continue

            try:
                data = response.json()
            except Exception as e:
                logger.warning("[LETTER_LLM] json parse failed. body=%s", response.text[:300])
                errors.append(f"{strategy.name}: invalid json ({e})")
                continue

            content, resolved_model = _parse_response_payload(
                strategy,
                data,
                model_to_use,
            )

            _cached_strategy = strategy
            _cached_models[strategy.url] = resolved_model

            logger.info(
                "[LETTER_LLM] success. strategy=%s resolved_model=%s content_len=%s",
                strategy.name,
                resolved_model,
                len(content),
            )

            return {
                "content": content,
                "model": resolved_model,
                "raw": data,
            }

    joined_errors = " | ".join(errors[:5]) if errors else "no strategies succeeded"

    raise LetterLLMError(
        "LLM 요청에 실패했습니다. "
        "LLM_BASE_URL이 OpenWebUI/Ollama 주소인지, 모델명이 실제 모델 ID와 맞는지 확인하세요. "
        f"details={joined_errors}"
    )