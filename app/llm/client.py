# backend/app/llm/client.py
import httpx
from app.core.config import settings


class LLMClient:
    async def generate(self, payload: dict) -> dict:
        timeout = httpx.Timeout(settings.LLM_TIMEOUT_SEC)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # ⚠️ LLM 서버가 "/"에서 받는다고 가정
            # 만약 404 뜨면 settings.LLM_BASE_URL을 ".../generate"로 바꾸면 끝
            resp = await client.post(settings.LLM_BASE_URL, json=payload)
            resp.raise_for_status()
            return resp.json()