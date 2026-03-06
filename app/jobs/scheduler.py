from __future__ import annotations

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from app.jobs.letter_jobs import generate_letters_for_today

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Seoul"))


def start_scheduler():
    # ✅ 이미 떠있으면 중복 start 방지
    if scheduler.running:
        logger.info("[SCHEDULER] already running, skip start")
        return

    # 매일 23:00 KST
    scheduler.add_job(
        generate_letters_for_today,
        trigger=CronTrigger(hour=23, minute=30),
        id="generate_letters_for_today",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 60,  # ✅ 1시간 내에 놓친 실행은 즉시 수행
    )
    scheduler.start()
    logger.info("[SCHEDULER] started (daily 23:30 KST)")