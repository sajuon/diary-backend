# /home/dori/diary-backend/app/services/diary_day.py
# 역할: '전날 일기 마감 시각' 공통 규칙.
#
# 마감 시각 = 편지 생성 배치 시각 (LETTER_GENERATE_HOUR/MINUTE, 기본 03:00 KST).
# - 자정 전에 화면에 들어와 자정을 넘겨 처음 저장한 전날 일기는 마감 전까지 당일 작성으로 인정
#   → 자동 답장, 스트릭, 일기 작성 보상(전날 기준) 모두 같은 기준을 쓴다.
# - 마감 전에 수정한 내용은 배치가 그대로 읽어 답장에 반영된다.

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.config import settings

KST = ZoneInfo("Asia/Seoul")

DIARY_DAY_CUTOFF = time(
    int(settings.LETTER_GENERATE_HOUR),
    int(settings.LETTER_GENERATE_MINUTE),
)
CUTOFF_DELTA = timedelta(hours=DIARY_DAY_CUTOFF.hour, minutes=DIARY_DAY_CUTOFF.minute)


def kst_now() -> datetime:
    return datetime.now(KST)


def created_within_day(entry_date: date, created_at_kst: datetime) -> bool:
    """created_at_kst(KST aware)가 entry_date 00:00 ~ 다음 날 마감 시각 이전인지."""
    start = datetime.combine(entry_date, time.min, tzinfo=KST)
    end = start + timedelta(days=1) + CUTOFF_DELTA
    return start <= created_at_kst < end


def day_window_utc_naive(entry_date: date) -> tuple[datetime, datetime]:
    """DB(UTC naive) 비교용 [entry_date 00:00, 다음 날 마감) 범위."""
    start = datetime.combine(entry_date, time.min, tzinfo=KST)
    end = start + timedelta(days=1) + CUTOFF_DELTA
    to_utc = lambda d: d.astimezone(timezone.utc).replace(tzinfo=None)
    return to_utc(start), to_utc(end)


def grace_previous_day(now: Optional[datetime] = None) -> Optional[date]:
    """지금이 자정~마감 사이면 전날 날짜, 아니면 None."""
    now = now or kst_now()
    if now.time() < DIARY_DAY_CUTOFF:
        return now.date() - timedelta(days=1)
    return None


def diary_reward_key(entry_date: date, now: Optional[datetime] = None) -> str:
    """
    일기 작성 보상의 하루 1회 키.
    - 기본: 작성한 날(KST)
    - 예외: 마감 전에 저장한 전날 일기 → 전날 키 (오늘 보상을 소진하지 않음)
    """
    now = now or kst_now()
    if entry_date == grace_previous_day(now):
        return entry_date.isoformat()
    return now.date().isoformat()
