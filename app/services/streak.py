from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.diary import DiaryEntry
from app.services.diary_day import created_within_day

KST = ZoneInfo("Asia/Seoul")


def kst_today_date() -> date:
    return datetime.now(KST).date()


def _to_kst(dt: datetime) -> datetime:
    """created_at은 DB(UTC)에서 naive로 올라오므로 KST로 변환."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


def is_on_time(entry_date: date, created_at: datetime) -> bool:
    """
    streak·자동 답장에 인정되는 '당일 작성분'인지.

    - 그 날짜(KST)에 처음 저장했거나
    - 다음 날 00:00 ~ 마감 시각(편지 배치 시각) 사이에 처음 저장한 경우
    마감 이후에 쓴 지난 일기는 소급 작성으로 보고 제외한다 (진주로 답장을 여는 대상).
    """
    return created_within_day(entry_date, _to_kst(created_at))


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