from __future__ import annotations

import json
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.monthly_report import MonthlyReport
from app.services.report_generator import generate_monthly_report
from app.services.streak import is_on_time

router = APIRouter(prefix="/api/reports", tags=["Reports"])

KST = ZoneInfo("Asia/Seoul")

MOOD_META = {
    "happy": {"label": "행복", "color": "#F2B84B", "group": "positive"},
    "excited": {"label": "설렘", "color": "#EFA0B4", "group": "positive"},
    "calm": {"label": "평온", "color": "#9DC49A", "group": "positive"},
    "grateful": {"label": "감사", "color": "#B6A5D6", "group": "positive"},
    "proud": {"label": "뿌듯함", "color": "#EE9463", "group": "positive"},
    "neutral": {"label": "무덤덤", "color": "#C2BFB4", "group": "neutral"},
    "blank": {"label": "멍함", "color": "#B3C0CB", "group": "neutral"},
    "tired": {"label": "피곤", "color": "#C6B49B", "group": "caution"},
    "worried": {"label": "걱정", "color": "#93B9BE", "group": "caution"},
    "sad": {"label": "슬픔", "color": "#A0BDD2", "group": "caution"},
    "upset": {"label": "속상함", "color": "#8BA0C6", "group": "caution"},
    "lonely": {"label": "외로움", "color": "#7A86A8", "group": "caution"},
    "angry": {"label": "화남", "color": "#C87A6C", "group": "caution"},
}

# 감정 키·라벨·색은 프론트 components/emotion-stone.tsx의 EMOTIONS와 맞춘다.
MOOD_ORDER = list(MOOD_META.keys())

WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


def kst_today() -> date:
    return datetime.now(KST).date()


def extract_mood(entry: DiaryEntry) -> Optional[str]:
    tags = entry.mood_tags
    if not tags or not isinstance(tags, list):
        return None
    first = tags[0]
    if not isinstance(first, str):
        return None
    return first if first in MOOD_META else None


def pick_day_entries(entries: list[DiaryEntry]) -> dict[date, DiaryEntry]:
    """하루에 free/question 둘 다 있으면 free 우선."""
    by_date: dict[date, dict[str, DiaryEntry]] = defaultdict(dict)

    for entry in entries:
        if not extract_mood(entry):
            continue
        diary_type = getattr(entry, "diary_type", None) or "free"
        by_date[entry.entry_date][diary_type] = entry

    result: dict[date, DiaryEntry] = {}
    for entry_date, type_map in by_date.items():
        if "free" in type_map:
            result[entry_date] = type_map["free"]
        else:
            result[entry_date] = next(iter(type_map.values()))

    return result


def day_mood_map(picked: dict[date, DiaryEntry]) -> dict[date, str]:
    return {d: extract_mood(e) for d, e in picked.items() if extract_mood(e)}


def build_mood_counts(counts: Counter) -> list[dict]:
    result = [
        {
            "mood": m,
            "label": MOOD_META[m]["label"],
            "color": MOOD_META[m]["color"],
            "count": counts.get(m, 0),
        }
        for m in MOOD_ORDER
        if counts.get(m, 0) > 0
    ]
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


def fetch_entries(db: Session, user_id: int, start: date, end: date) -> list[DiaryEntry]:
    return (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == user_id,
            DiaryEntry.entry_date >= start,
            DiaryEntry.entry_date <= end,
        )
        .all()
    )


def on_time_dates(entries: list[DiaryEntry]) -> set[date]:
    """연속 기록에 인정되는 날짜 (streak.py와 같은 기준: 당일 작성분만)."""
    return {
        e.entry_date
        for e in entries
        if e.created_at is not None and is_on_time(e.entry_date, e.created_at)
    }


def calc_longest_streak(dates: set[date]) -> int:
    longest = 0
    current = 0
    prev: Optional[date] = None
    for d in sorted(dates):
        current = current + 1 if prev is not None and (d - prev).days == 1 else 1
        longest = max(longest, current)
        prev = d
    return longest


def compute_stats(
    day_moods: dict[date, str],
    total_days: int,
    prev_counts: Counter,
    streak_dates: set[date],
) -> dict:
    """LLM 프롬프트에 넘길 관찰 데이터."""
    if not day_moods:
        return {"total_days": total_days, "recorded_days": 0}

    counts = Counter(day_moods.values())
    sorted_dates = sorted(day_moods.keys())

    recovery_gaps: list[int] = []
    pending: Optional[date] = None

    for entry_date in sorted_dates:
        group = MOOD_META[day_moods[entry_date]]["group"]
        if group == "caution" and pending is None:
            pending = entry_date
        elif group == "positive" and pending is not None:
            recovery_gaps.append((entry_date - pending).days)
            pending = None

    caution_by_weekday = Counter()
    for entry_date, mood in day_moods.items():
        if MOOD_META[mood]["group"] == "caution":
            caution_by_weekday[entry_date.weekday()] += 1

    longest = calc_longest_streak(streak_dates)

    stats: dict = {
        "total_days": total_days,
        "recorded_days": len(day_moods),
        "longest_streak": longest,
        "positive_days": sum(
            c for m, c in counts.items() if MOOD_META[m]["group"] == "positive"
        ),
        "caution_days": sum(
            c for m, c in counts.items() if MOOD_META[m]["group"] == "caution"
        ),
    }

    if recovery_gaps:
        stats["avg_recovery"] = round(sum(recovery_gaps) / len(recovery_gaps), 1)

    if caution_by_weekday:
        worst_day, worst_count = caution_by_weekday.most_common(1)[0]
        if worst_count >= 2:
            stats["hard_weekday"] = WEEKDAY_LABELS[worst_day]
            stats["hard_weekday_count"] = worst_count

    if prev_counts:
        prev_top = prev_counts.most_common(1)[0][0]
        prev_label = MOOD_META[prev_top]["label"]
        diff = counts.get(prev_top, 0) - prev_counts[prev_top]
        if diff > 0:
            stats["prev_month_diff"] = f"지난달 많았던 '{prev_label}' 감정인 날이 {diff}일 늘었음"
        elif diff < 0:
            stats["prev_month_diff"] = (
                f"지난달 많았던 '{prev_label}' 감정인 날이 {abs(diff)}일 줄었음"
            )

    return stats


def build_day_summaries(
    picked: dict[date, DiaryEntry],
    day_moods: dict[date, str],
) -> list[dict]:
    result = []
    for entry_date in sorted(picked.keys()):
        entry = picked[entry_date]
        mood = day_moods[entry_date]
        result.append(
            {
                "date": entry_date.isoformat(),
                "label": MOOD_META[mood]["label"],
                "summary_tag": getattr(entry, "summary_tag", None),
                "content": entry.content,
            }
        )
    return result


class MoodCount(BaseModel):
    mood: str
    label: str
    color: str
    count: int


class DayMood(BaseModel):
    date: str
    day: int
    weekday: int
    mood: Optional[str] = None
    label: Optional[str] = None
    color: Optional[str] = None


class MonthlyReportResponse(BaseModel):
    year: int
    month: int
    days: list[DayMood]
    mood_counts: list[MoodCount]
    recorded_days: int
    total_days: int
    top_mood: Optional[str] = None
    top_mood_label: Optional[str] = None
    positive_days: int
    caution_days: int
    available_months: list[str]
    prev_month: Optional[str] = None
    next_month: Optional[str] = None


class WeeklyDay(BaseModel):
    date: str
    weekday: int
    weekday_label: str
    mood: Optional[str] = None
    label: Optional[str] = None
    color: Optional[str] = None
    summary_tag: Optional[str] = None


class WeeklyReportResponse(BaseModel):
    start_date: str
    end_date: str
    days: list[WeeklyDay]
    mood_counts: list[MoodCount]
    recorded_days: int
    top_mood_label: Optional[str] = None
    highlights: list[str]
    comment: str
    has_prev: bool
    has_next: bool


class MonthlySummaryResponse(BaseModel):
    year: int
    month: int
    insights: list[str]
    summary: str
    highlights: list[str]
    comment: str
    source_type: str
    cached: bool


@router.get("/monthly", response_model=MonthlyReportResponse)
def get_monthly_report(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today()
    year = year or today.year
    month = month or today.month

    total_days = monthrange(year, month)[1]
    first_day = date(year, month, 1)
    last_day = date(year, month, total_days)

    picked = pick_day_entries(fetch_entries(db, user.id, first_day, last_day))
    day_moods = day_mood_map(picked)

    days: list[DayMood] = []
    for d in range(1, total_days + 1):
        current = date(year, month, d)
        mood = day_moods.get(current)
        meta = MOOD_META.get(mood) if mood else None
        days.append(
            DayMood(
                date=current.isoformat(),
                day=d,
                weekday=current.weekday(),
                mood=mood,
                label=meta["label"] if meta else None,
                color=meta["color"] if meta else None,
            )
        )

    counts = Counter(day_moods.values())

    all_dates = (
        db.query(DiaryEntry.entry_date)
        .filter(DiaryEntry.user_id == user.id)
        .distinct()
        .all()
    )
    available = sorted({f"{r[0].year:04d}-{r[0].month:02d}" for r in all_dates})

    current_key = f"{year:04d}-{month:02d}"
    earlier = [m for m in available if m < current_key]
    later = [m for m in available if m > current_key]

    top_mood = counts.most_common(1)[0][0] if counts else None

    return MonthlyReportResponse(
        year=year,
        month=month,
        days=days,
        mood_counts=[MoodCount(**c) for c in build_mood_counts(counts)],
        recorded_days=len(day_moods),
        total_days=total_days,
        top_mood=top_mood,
        top_mood_label=MOOD_META[top_mood]["label"] if top_mood else None,
        positive_days=sum(
            c for m, c in counts.items() if MOOD_META[m]["group"] == "positive"
        ),
        caution_days=sum(
            c for m, c in counts.items() if MOOD_META[m]["group"] == "caution"
        ),
        available_months=available,
        prev_month=earlier[-1] if earlier else None,
        next_month=later[0] if later else None,
    )


def week_range(target: date) -> tuple[date, date]:
    """일요일 시작, 토요일 종료."""
    offset = (target.weekday() + 1) % 7
    start = target - timedelta(days=offset)
    return start, start + timedelta(days=6)


def build_weekly_comment(day_moods: dict[date, str], recorded: int) -> str:
    if not day_moods:
        return "이번 주는 아직 기록이 없네요. 짧게라도 남겨두면 나중에 돌아볼 게 생겨요."

    counts = Counter(day_moods.values())
    top_mood = counts.most_common(1)[0][0]
    top_label = MOOD_META[top_mood]["label"]

    sorted_dates = sorted(day_moods.keys())
    first_group = MOOD_META[day_moods[sorted_dates[0]]]["group"]
    last_group = MOOD_META[day_moods[sorted_dates[-1]]]["group"]

    if first_group == "caution" and last_group == "positive":
        flow = "초반엔 조금 지쳐 보였는데, 뒤로 갈수록 안정되는 흐름이었어요."
    elif first_group == "positive" and last_group == "caution":
        flow = "초반은 괜찮았는데 뒤로 갈수록 지친 기색이 보여요."
    else:
        flow = "한 주 내내 비슷한 결의 감정이 이어졌어요."

    return f"이번 주는 '{top_label}' 감정인 날이 가장 많았어요. {flow}"


@router.get("/weekly", response_model=WeeklyReportResponse)
def get_weekly_report(
    offset: int = Query(0, description="0=이번 주, -1=지난 주"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today()
    base = today + timedelta(weeks=offset)
    start, end = week_range(base)

    picked = pick_day_entries(fetch_entries(db, user.id, start, end))
    day_moods = day_mood_map(picked)

    days: list[WeeklyDay] = []
    for i in range(7):
        current = start + timedelta(days=i)
        entry = picked.get(current)
        mood = day_moods.get(current)
        meta = MOOD_META.get(mood) if mood else None
        days.append(
            WeeklyDay(
                date=current.isoformat(),
                weekday=current.weekday(),
                weekday_label=WEEKDAY_LABELS[current.weekday()],
                mood=mood,
                label=meta["label"] if meta else None,
                color=meta["color"] if meta else None,
                summary_tag=getattr(entry, "summary_tag", None) if entry else None,
            )
        )

    counts = Counter(day_moods.values())
    recorded = len(day_moods)

    highlights: list[str] = []

    if counts:
        top_mood, top_count = counts.most_common(1)[0]
        highlights.append(f"가장 자주 나온 감정: {MOOD_META[top_mood]['label']} · {top_count}일")

    tags = [d.summary_tag for d in days if d.summary_tag and d.summary_tag.strip()]
    if tags:
        highlights.append(f"이번 주 키워드: {' '.join(tags[:3])}")

    highlights.append(f"기록한 날: 7일 중 {recorded}일")

    earliest = (
        db.query(DiaryEntry.entry_date)
        .filter(DiaryEntry.user_id == user.id)
        .order_by(DiaryEntry.entry_date.asc())
        .first()
    )

    return WeeklyReportResponse(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        days=days,
        mood_counts=[MoodCount(**c) for c in build_mood_counts(counts)],
        recorded_days=recorded,
        top_mood_label=(
            MOOD_META[counts.most_common(1)[0][0]]["label"] if counts else None
        ),
        highlights=highlights,
        comment=build_weekly_comment(day_moods, recorded),
        has_prev=bool(earliest and earliest[0] < start),
        has_next=end < today,
    )


@router.get("/monthly-summary", response_model=MonthlySummaryResponse)
async def get_monthly_summary(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today()
    year = year or today.year
    month = month or today.month

    total_days = monthrange(year, month)[1]
    first_day = date(year, month, 1)
    last_day = date(year, month, total_days)

    entries = fetch_entries(db, user.id, first_day, last_day)
    picked = pick_day_entries(entries)
    day_moods = day_mood_map(picked)
    entry_count = len(day_moods)

    cached = (
        db.query(MonthlyReport)
        .filter(
            MonthlyReport.user_id == user.id,
            MonthlyReport.year == year,
            MonthlyReport.month == month,
        )
        .first()
    )

    if cached and cached.entry_count == entry_count and cached.insights:
        return MonthlySummaryResponse(
            year=year,
            month=month,
            insights=json.loads(cached.insights),
            summary=cached.summary,
            highlights=json.loads(cached.highlights),
            comment=cached.comment,
            source_type=cached.source_type,
            cached=True,
        )

    prev_last = first_day - timedelta(days=1)
    prev_picked = pick_day_entries(
        fetch_entries(db, user.id, date(prev_last.year, prev_last.month, 1), prev_last)
    )
    prev_counts = Counter(day_mood_map(prev_picked).values())

    counts = Counter(day_moods.values())
    mood_counts = build_mood_counts(counts)
    day_summaries = build_day_summaries(picked, day_moods)
    stats = compute_stats(day_moods, total_days, prev_counts, on_time_dates(entries))

    report, source_type, model_name = await generate_monthly_report(
        year, month, mood_counts, day_summaries, stats
    )

    insights_json = json.dumps(report["insights"], ensure_ascii=False)
    highlights_json = json.dumps(report["highlights"], ensure_ascii=False)

    if cached:
        cached.summary = report["summary"]
        cached.highlights = highlights_json
        cached.comment = report["comment"]
        cached.insights = insights_json
        cached.entry_count = entry_count
        cached.source_type = source_type
        cached.model_name = model_name
    else:
        cached = MonthlyReport(
            user_id=user.id,
            year=year,
            month=month,
            summary=report["summary"],
            highlights=highlights_json,
            comment=report["comment"],
            insights=insights_json,
            entry_count=entry_count,
            source_type=source_type,
            model_name=model_name,
        )
        db.add(cached)

    db.commit()

    return MonthlySummaryResponse(
        year=year,
        month=month,
        insights=report["insights"],
        summary=report["summary"],
        highlights=report["highlights"],
        comment=report["comment"],
        source_type=source_type,
        cached=False,
    )