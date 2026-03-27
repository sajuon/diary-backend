from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune
from app.models.letter import OtterLetter
from app.services.letter_generator import generate_otter_letter
from app.services.web_push import send_web_push_to_user

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


def kst_now():
    return datetime.now(KST)


def previous_day_date():
    return (kst_now() - timedelta(days=1)).date()


def _reply_notification_title() -> str:
    return "해도리가 답장을 보냈어요!"


def _reply_notification_body(diary_date) -> str:
    return f"{diary_date.month}월 {diary_date.day}일 일기에 대한 편지가 도착했어요."


async def generate_letters_for_previous_day():
    """
    매일 00:00 KST에 실행:
    - 전날 일기 쓴 유저들 중
    - 아직 해당 일기에 대한 편지가 없는 경우
    - 편지 생성해서 저장
    - 편지 날짜(letter_date)는 전날 날짜로 저장
    """
    diary_date = previous_day_date()

    logger.info(
        "[SCHEDULER] generate_letters_for_previous_day started. diary_date=%s",
        diary_date,
    )

    db: Session = SessionLocal()

    created = 0
    skipped_exists = 0
    skipped_no_user = 0
    failed = 0

    try:
        diaries = db.query(DiaryEntry).filter(DiaryEntry.entry_date == diary_date).all()

        if not diaries:
            logger.info("[SCHEDULER] no diaries for diary_date=%s. done.", diary_date)
            return

        for entry in diaries:
            try:
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
                        DailyFortune.fortune_date == diary_date,
                    )
                    .first()
                )

                data = await generate_otter_letter(
                    user=user,
                    diary_entry=entry,
                    fortune=fortune,
                )

                letter = OtterLetter(
                    user_id=user.id,
                    diary_entry_id=entry.id,
                    letter_date=diary_date,
                    content=data.get("content", ""),
                    element_hint=data.get("element_hint"),
                    model=data.get("model"),
                    is_read=False,
                    read_at=None,
                )

                db.add(letter)
                db.commit()
                created += 1

            except Exception as e:
                db.rollback()
                failed += 1
                logger.exception(
                    "[SCHEDULER] failed for diary_entry_id=%s: %s",
                    entry.id,
                    e,
                )
                continue

        logger.info(
            "[SCHEDULER] done. diary_date=%s created=%s skipped_exists=%s skipped_no_user=%s failed=%s",
            diary_date,
            created,
            skipped_exists,
            skipped_no_user,
            failed,
        )

    finally:
        db.close()


async def send_reply_notifications_for_previous_day():
    """
    매일 06:00 KST에 실행:
    - 전날 일기에 대한 편지가 생성된 유저 중
    - 아직 읽지 않은 편지가 있는 경우
    - 웹 푸시 알림 전송
    """
    diary_date = previous_day_date()

    logger.info(
        "[SCHEDULER] send_reply_notifications_for_previous_day started. diary_date=%s",
        diary_date,
    )

    # If the midnight generation job was missed or the app restarted late,
    # make sure the previous day's letters exist before sending pushes.
    await generate_letters_for_previous_day()

    db: Session = SessionLocal()

    processed = 0
    sent = 0
    skipped = 0

    try:
        letters = (
            db.query(OtterLetter)
            .filter(
                OtterLetter.letter_date == diary_date,
                OtterLetter.is_read == False,
                OtterLetter.reply_notified_at == None,
            )
            .order_by(OtterLetter.id.asc())
            .all()
        )

        if not letters:
            logger.info(
                "[SCHEDULER] no unread letters for diary_date=%s. done.",
                diary_date,
            )
            return

        title = _reply_notification_title()
        body = _reply_notification_body(diary_date)

        for letter in letters:
            result = send_web_push_to_user(
                db=db,
                user_id=letter.user_id,
                title=title,
                body=body,
                url=f"/letter-detail/{letter.id}",
                notification_type="reply",
            )
            processed += 1
            sent += int(result.get("sent") or 0)
            skipped += int(result.get("skipped") or 0)

            if (result.get("sent") or 0) > 0:
                letter.reply_notified_at = kst_now()
                db.commit()

            logger.info(
                "[SCHEDULER] reply push processed. letter_id=%s user_id=%s sent=%s skipped=%s reason=%s",
                letter.id,
                letter.user_id,
                result.get("sent"),
                result.get("skipped"),
                result.get("reason"),
            )

        logger.info(
            "[SCHEDULER] reply push done. diary_date=%s processed=%s sent=%s skipped=%s",
            diary_date,
            processed,
            sent,
            skipped,
        )
    finally:
        db.close()
