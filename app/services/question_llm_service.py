from __future__ import annotations

import hashlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.diary_question import DiaryQuestion
from app.models.user import User
from app.services.letter_llm_service import LetterLLMError, request_letter_llm
from app.services.prompt_templates import (
    build_question_user_prompt,
    fallback_question_candidates,
    question_system_prompt,
)

KST = ZoneInfo("Asia/Seoul")


def kst_today_date():
    return datetime.now(KST).date()


def normalize_question(text: str) -> str:
    text = text.strip()
    text = text.replace('"', "").replace("“", "").replace("”", "")
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    if "\n" in text:
        text = text.splitlines()[0].strip()

    text = text.rstrip(".。!！")
    if not text.endswith("?"):
        text = f"{text}?"

    return text


def hash_question(text: str) -> str:
    normalized = normalize_question(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def call_question_llm(previous_questions: list[str]) -> tuple[str, str]:
    payload = {
        "model": settings.QUESTION_LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": question_system_prompt(),
            },
            {
                "role": "user",
                "content": build_question_user_prompt(previous_questions),
            },
        ],
        "temperature": 0.95,
        "max_tokens": 120,
    }

    result = await request_letter_llm(payload)
    question = normalize_question((result.get("content") or "").strip())
    model_name = result.get("model") or settings.QUESTION_LLM_MODEL

    if not question:
        raise LetterLLMError("질문 생성 결과가 비어 있습니다.")

    return question, model_name


def pick_fallback_question(previous_hashes: set[str]) -> str:
    for question in fallback_question_candidates():
        if hash_question(question) not in previous_hashes:
            return normalize_question(question)

    raise LetterLLMError("사용 가능한 fallback 질문이 없습니다.")


async def get_or_create_today_question(
    db: Session,
    user: User,
) -> dict:
    today = kst_today_date()

    existing = (
        db.query(DiaryQuestion)
        .filter(
            DiaryQuestion.user_id == user.id,
            DiaryQuestion.entry_date == today,
        )
        .first()
    )

    if existing:
        return {
            "question": existing.question_text,
            "model": existing.model_name,
            "source_type": existing.source_type,
            "entry_date": existing.entry_date,
            "created_at": existing.created_at,
            "cached": True,
        }

    previous_rows = (
        db.query(DiaryQuestion.question_text, DiaryQuestion.question_hash)
        .filter(DiaryQuestion.user_id == user.id)
        .order_by(DiaryQuestion.created_at.desc())
        .all()
    )

    previous_questions = [row[0] for row in previous_rows]
    previous_hashes = {row[1] for row in previous_rows}

    question_text = None
    model_name = None
    source_type = "llm"

    for _ in range(5):
        generated_text, generated_model = await call_question_llm(previous_questions)
        generated_hash = hash_question(generated_text)

        if generated_hash not in previous_hashes:
            question_text = generated_text
            model_name = generated_model
            break

    if not question_text:
        question_text = pick_fallback_question(previous_hashes)
        model_name = settings.QUESTION_LLM_MODEL
        source_type = "fallback"

    question_hash = hash_question(question_text)

    row = DiaryQuestion(
        user_id=user.id,
        entry_date=today,
        question_text=question_text,
        question_hash=question_hash,
        model_name=model_name,
        source_type=source_type,
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "question": row.question_text,
        "model": row.model_name,
        "source_type": row.source_type,
        "entry_date": row.entry_date,
        "created_at": row.created_at,
        "cached": False,
    }