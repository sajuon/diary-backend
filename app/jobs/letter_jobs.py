# backend/app/jobs/letter_jobs.py

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune
from app.models.letter import OtterLetter
from app.services.letter_generator import generate_otter_letter

logger = logging.getLogger(__name__)


def kst_today_date():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


async def generate_letters_for_today():
    """
    매일 23:00에 실행:
    - 오늘 일기 쓴 유저들 중
    - 아직 오늘 편지가 없는 경우
    - 편지 생성해서 저장
    """
    today = kst_today_date()
    logger.info("[SCHEDULER] generate_letters_for_today started. today=%s", today)

    db: Session = SessionLocal()

    created = 0
    skipped_exists = 0
    skipped_no_user = 0
    failed = 0

    try:
        # 오늘 일기 전체
        diaries = db.query(DiaryEntry).filter(DiaryEntry.entry_date == today).all()

        if not diaries:
            logger.info("[SCHEDULER] no diaries for today. done.")
            return

        for entry in diaries:
            try:
                # 이미 오늘 편지 있으면 skip
                exists = (
                    db.query(OtterLetter)
                    .filter(OtterLetter.diary_entry_id == entry.id)
                    .first()
                )
                if exists:
                    skipped_exists += 1
                    continue

                user = db.query(User).filter(User.id == entry.user_id).first()
                if not user:
                    skipped_no_user += 1
                    continue

                fortune = (
                    db.query(DailyFortune)
                    .filter(
                        DailyFortune.user_id == user.id,
                        DailyFortune.fortune_date == today,
                    )
                    .first()
                )

                data = await generate_otter_letter(
                    user=user, diary_entry=entry, fortune=fortune
                )

                letter = OtterLetter(
                    user_id=user.id,
                    diary_entry_id=entry.id,
                    letter_date=today,
                    content=data.get("content", ""),
                    element_hint=data.get("element_hint"),
                    model=data.get("model"),
                )

                db.add(letter)
                db.commit()  # ✅ 한 건씩 커밋해서 실패 격리
                created += 1

            except Exception as e:
                db.rollback()
                failed += 1
                logger.exception(
                    "[SCHEDULER] failed for diary_entry_id=%s: %s", entry.id, e
                )
                continue

        logger.info(
            "[SCHEDULER] done. created=%s skipped_exists=%s skipped_no_user=%s failed=%s",
            created,
            skipped_exists,
            skipped_no_user,
            failed,
        )

    finally:
        db.close()