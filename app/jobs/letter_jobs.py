from __future__ import annotations

import logging
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune
from app.models.letter import OtterLetter
from app.services.letter_generator import generate_otter_letter
from app.services.streak import is_on_time, late_grace
from app.services.web_push import send_web_push_to_user

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

TARGET_TODAY = bool(settings.LETTER_TARGET_TODAY)

# 다시 시도해도 결과가 같은 푸시 생략 사유 (web_push.send_web_push_to_user의 reason)
FINAL_SKIP_REASONS = {
    "push_disabled",
    "reply_disabled",
    "no_active_subscriptions",
}


def kst_now():
    return datetime.now(KST)


def previous_day_date():
    return (kst_now() - timedelta(days=1)).date()


def today_date():
    return kst_now().date()


def target_diary_date():
    """
    편지 생성/푸시 대상 날짜.
    - 기본(운영): 전날
    - LETTER_TARGET_TODAY=true (실험용): 오늘
    """
    return today_date() if TARGET_TODAY else previous_day_date()


def kst_day_bounds_utc(target_date):
    """
    KST 기준 하루를 DB 비교용 UTC naive 범위 [start, end)로 변환.
    diary_entries.created_at은 UTC naive로 저장된다 (MySQL time_zone=UTC).
    """
    start = (
        datetime.combine(target_date, time.min, tzinfo=KST)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    return start, start + timedelta(days=1)


def _reply_notification_title() -> str:
    return "해도리가 답장을 보냈어요!"


def _reply_notification_body(diary_date) -> str:
    return f"{diary_date.month}월 {diary_date.day}일 일기에 대한 편지가 도착했어요."


async def generate_letters_for_previous_day():
    """
    스케줄된 시각에 실행:
    - 대상 날짜(기본 전날, LETTER_TARGET_TODAY=true면 오늘)의 일기 중
    - 그 날짜 0시 ~ 다음 날 배치 시각 전에 작성한 일기만 자동 답장 생성 (streak.is_on_time)
    - 즉, 뒤늦게 작성한 과거 날짜 일기는 자동 답장 생성 X
    """
    diary_date = target_diary_date()

    logger.info(
        "[SCHEDULER] generate_letters started. diary_date=%s target_today=%s",
        diary_date,
        TARGET_TODAY,
    )

    db: Session = SessionLocal()

    created = 0
    skipped_exists = 0
    skipped_no_user = 0
    skipped_late_written = 0
    failed = 0

    try:
        start_dt, end_dt = kst_day_bounds_utc(diary_date)
        # 배치 시각 전까지 쓴 전날 일기도 포함 (최종 판정은 아래 is_on_time)
        end_dt = end_dt + late_grace()

        diaries = (
            db.query(DiaryEntry)
            .filter(
                DiaryEntry.entry_date == diary_date,
                DiaryEntry.created_at >= start_dt,
                DiaryEntry.created_at < end_dt,
                DiaryEntry.diary_type == "free",
            )
            .all()
        )

        if not diaries:
            logger.info(
                "[SCHEDULER] no eligible diaries for diary_date=%s. done.",
                diary_date,
            )
            return

        logger.info(
            "[SCHEDULER] %s eligible diaries found for diary_date=%s",
            len(diaries),
            diary_date,
        )

        for entry in diaries:
            try:
                # streak.py와 같은 기준: 그 날짜 ~ 다음 날 배치 시각 전에 쓴 일기만 자동 답장
                if entry.created_at is None or not is_on_time(
                    entry.entry_date, entry.created_at
                ):
                    skipped_late_written += 1
                    logger.info(
                        "[SCHEDULER] skipped late-written diary. entry_id=%s entry_date=%s created_at=%s",
                        entry.id,
                        entry.entry_date,
                        entry.created_at,
                    )
                    continue

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
            "[SCHEDULER] done. diary_date=%s created=%s skipped_exists=%s skipped_no_user=%s skipped_late_written=%s failed=%s",
            diary_date,
            created,
            skipped_exists,
            skipped_no_user,
            skipped_late_written,
            failed,
        )

    finally:
        db.close()


async def send_reply_notifications_for_previous_day():
    """
    스케줄된 시각에 실행:
    - 대상 날짜에 정상 작성된 일기에 대한 편지가 생성된 유저 중
    - 아직 읽지 않은 편지가 있는 경우
    - 웹 푸시 알림 전송
    """
    diary_date = target_diary_date()

    logger.info(
        "[SCHEDULER] send_reply_notifications started. diary_date=%s target_today=%s",
        diary_date,
        TARGET_TODAY,
    )

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

            # 처리 완료로 기록 → 재시작(startup catch-up)마다 같은 편지를 다시 시도하지 않음
            # - 보냄 / 보낼 곳 없음(구독 없음·알림 꺼짐)은 완료
            # - 구독은 있는데 전부 실패한 경우만 다음 실행에서 재시도
            if (result.get("sent") or 0) > 0 or result.get("reason") in FINAL_SKIP_REASONS:
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