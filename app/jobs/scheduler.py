from __future__ import annotations

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from app.jobs.letter_jobs import (
    generate_letters_for_previous_day,
    send_reply_notifications_for_previous_day,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
scheduler = AsyncIOScheduler(timezone=KST)
DAILY_JOB_MISFIRE_GRACE_SEC = 12 * 60 * 60


def start_scheduler():
    if scheduler.running:
        logger.info("[SCHEDULER] already running, skip start")
        return

    # 매일 00:00 KST, 전날 일기에 대한 편지 생성
    scheduler.add_job(
        generate_letters_for_previous_day,
        trigger=CronTrigger(hour=0, minute=0, timezone=KST),
        id="generate_letters_for_previous_day",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=DAILY_JOB_MISFIRE_GRACE_SEC,
    )

    # 매일 06:00 KST, 전날 생성된 편지에 대한 푸시 알림 발송
    scheduler.add_job(
        send_reply_notifications_for_previous_day,
        trigger=CronTrigger(hour=6, minute=0, timezone=KST),
        id="send_reply_notifications_for_previous_day",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=DAILY_JOB_MISFIRE_GRACE_SEC,
    )

    scheduler.start()
    logger.info(
        "[SCHEDULER] started (generate 00:00 KST, reply push 06:00 KST for previous day diaries)"
    )


async def run_startup_catchup():
    now = datetime.now(KST)

    if now.hour >= 6:
        logger.info(
            "[SCHEDULER] startup catch-up: ensuring previous-day letters and reply pushes are up to date"
        )
        await send_reply_notifications_for_previous_day()
        return

    logger.info(
        "[SCHEDULER] startup catch-up: ensuring previous-day letters are up to date"
    )
    await generate_letters_for_previous_day()
