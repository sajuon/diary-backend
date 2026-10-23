from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.diary import DiaryEntry

KST = ZoneInfo("Asia/Seoul")


def late_grace() -> timedelta:
    """
    전날 일기 인정 유예: 편지 배치 시각(LETTER_GENERATE_*)까지.
    예) 배치 03:00 → 다음 날 02:59:59까지 쓴 전날 일기는 그날 쓴 것으로 본다.
    실험 모드(LETTER_TARGET_TODAY)는 오늘 일기를 대상으로 하므로 유예 없음.
    """
    if settings.LETTER_TARGET_TODAY:
        return timedelta(0)
    return timedelta(
        hours=int(settings.LETTER_GENERATE_HOUR),
        minutes=int(settings.LETTER_GENERATE_MINUTE),
    )


def on_time_deadline(entry_date: date) -> datetime:
    """entry_date 일기가 '제때 쓴 일기'로 인정되는 마감 시각 (KST, 이 시각 미만)."""
    return datetime.combine(entry_date + timedelta(days=1), time.min, tzinfo=KST) + late_grace()


def kst_today_date() -> date:
    return datetime.now(KST).date()


def _to_kst(dt: datetime) -> datetime:
    """created_at은 DB(UTC)에서 naive로 올라오므로 KST로 변환."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


def is_on_time(entry_date: date, created_at: datetime) -> bool:
    """
    streak·자동 답장·작성 보상에 인정되는 '제때 쓴 일기'인지.

    그날 0시부터 다음 날 편지 배치 시각 전까지 작성하면 인정한다.
    (자정 전에 쓰기 시작해 자정을 넘겨 저장한 경우 포함)
    그 이후에 쓴 지난 일기는 소급 작성으로 보고 연속·자동 답장에서 제외한다.
    """
    written = _to_kst(created_at)
    start = datetime.combine(entry_date, time.min, tzinfo=KST)
    return start <= written < on_time_deadline(entry_date)


def calc_streak_summary(db: Session, user_id: int) -> dict:
    """
    streak 계산.

    - streak       : 실제 연속일수 (오늘 안 썼으면 어제까지 기준)
    - streak_n     : 화면 표시용. 오늘 안 썼으면 '오늘 쓰면 될 숫자'라 +1
    - has_today    : 오늘 일기 존재 여부 (소급 여부 무관)
    - total_diaries: 전체 일기 수 (소급 포함)
    """
    today = kst_today_date()

    rows = (
        db.query(DiaryEntry.entry_date, DiaryEntry.created_at)
        .filter(DiaryEntry.user_id == user_id)
        .all()
    )

    all_dates = {r[0] for r in rows}
    streak_dates = {
        entry_date
        for entry_date, created_at in rows
        if created_at is not None and is_on_time(entry_date, created_at)
    }

    has_today = today in all_dates

    start = today if today in streak_dates else (today - timedelta(days=1))

    streak = 0
    d = start
    while d in streak_dates:
        streak += 1
        d -= timedelta(days=1)

    streak_n = streak if has_today else (streak + 1)

    return {
        "streak": streak,
        "streak_n": streak_n,
        "has_today": has_today,
        "total_diaries": len(rows),
    }