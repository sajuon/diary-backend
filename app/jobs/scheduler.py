from __future__ import annotations

import logging
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.jobs.letter_jobs import (
    generate_letters_for_previous_day,
    send_reply_notifications_for_previous_day,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
scheduler = AsyncIOScheduler(timezone=KST)
DAILY_JOB_MISFIRE_GRACE_SEC = 12 * 60 * 60

GENERATE_HOUR = int(settings.LETTER_GENERATE_HOUR)
GENERATE_MINUTE = int(settings.LETTER_GENERATE_MINUTE)
PUSH_HOUR = int(settings.LETTER_PUSH_HOUR)
PUSH_MINUTE = int(settings.LETTER_PUSH_MINUTE)

GENERATE_TIME = time(GENERATE_HOUR, GENERATE_MINUTE)
PUSH_TIME = time(PUSH_HOUR, PUSH_MINUTE)


def start_scheduler():
    if scheduler.running:
        logger.info("[SCHEDULER] already running, skip start")
        return

    # 전날 일기에 대한 편지 생성 (LLM 배치) — 시각은 .env에서 관리
    scheduler.add_job(
        generate_letters_for_previous_day,
        trigger=CronTrigger(hour=GENERATE_HOUR, minute=GENERATE_MINUTE, timezone=KST),
        id="generate_letters_for_previous_day",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=DAILY_JOB_MISFIRE_GRACE_SEC,
    )

    # 생성된 편지에 대한 푸시 알림 발송 — 시각은 .env에서 관리
    scheduler.add_job(
        send_reply_notifications_for_previous_day,
        trigger=CronTrigger(hour=PUSH_HOUR, minute=PUSH_MINUTE, timezone=KST),
        id="send_reply_notifications_for_previous_day",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=DAILY_JOB_MISFIRE_GRACE_SEC,
    )

    scheduler.start()
    logger.info(
        "[SCHEDULER] started (generate %02d:%02d KST, reply push %02d:%02d KST for previous day diaries)",
        GENERATE_HOUR,
        GENERATE_MINUTE,
        PUSH_HOUR,
        PUSH_MINUTE,
    )


async def run_startup_catchup():
    now = datetime.now(KST)
    now_time = now.time()

    if now_time >= PUSH_TIME:
        logger.info(
            "[SCHEDULER] startup catch-up: letters + reply pushes (now=%s KST, generate=%s, push=%s)",
            now_time.strftime("%H:%M"),
            GENERATE_TIME.strftime("%H:%M"),
            PUSH_TIME.strftime("%H:%M"),
        )
        await generate_letters_for_previous_day()
        await send_reply_notifications_for_previous_day()
        return

    if now_time >= GENERATE_TIME:
        logger.info(
            "[SCHEDULER] startup catch-up: letters only (now=%s KST, generate=%s)",
            now_time.strftime("%H:%M"),
            GENERATE_TIME.strftime("%H:%M"),
        )
        await generate_letters_for_previous_day()
        return

    logger.info(
        "[SCHEDULER] startup catch-up: skipped (now=%s KST is before generate time %s)",
        now_time.strftime("%H:%M"),
        GENERATE_TIME.strftime("%H:%M"),
    )