from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from app.jobs.letter_jobs import generate_letters_for_today

scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Seoul"))


def start_scheduler():
    # 매일 23:00 KST
    scheduler.add_job(
        generate_letters_for_today,
        trigger=CronTrigger(hour=23, minute=0),
        id="generate_letters_for_today",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()