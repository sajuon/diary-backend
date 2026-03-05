# app/services/openwebui_client.py

from __future__ import annotations

from typing import Any, Dict, Optional
import requests

from app.core.config import settings


class OpenWebUIClient:
    """
    Open WebUI OpenAI-compatible endpoint client
    - /api/chat/completions
    """

    def __init__(self) -> None:
        base = settings.LLM_BASE_URL.rstrip("/")
        self.base_url = base
        self.timeout = settings.LLM_TIMEOUT_SEC

        if not settings.LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY is missing (.env에 넣어야 함)")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            }
        )

    def chat(
        self,
        user_text: str,
        system_text: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 400,
    ) -> str:
        url = f"{self.base_url}/api/chat/completions"

        messages = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": user_text})

        payload: Dict[str, Any] = {
            "model": model or settings.LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        r = self.session.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()

        # ✅ 서비스에서는 content만 사용 (reasoning_content 같은 거 무시)
        return data["choices"][0]["message"]["content"]