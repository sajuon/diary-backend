from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.schemas.diary import DiaryCreateRequest, DiaryEntryResponse


router = APIRouter(prefix="/api/diary", tags=["Diary"])

# GET /api/diary/today 엔드포인트를 router 선언 이후로 이동
@router.get("/today", response_model=DiaryEntryResponse)
def get_today_diary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today_date()
    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == today)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="오늘 일기가 없습니다")
    return entry


def kst_today_date():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


@router.post("/today", response_model=DiaryEntryResponse)
def create_today_diary(
    data: DiaryCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today_date()

    exists = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == today)
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="오늘 일기는 이미 작성했습니다",
        )

    entry = DiaryEntry(
        user_id=user.id,
        entry_date=today,
        content=data.content,
        mood_tags=data.mood_tags,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/date/{date}", response_model=DiaryEntryResponse)
def get_diary_by_date(
    date: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        entry_date = datetime.fromisoformat(date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 날짜 형식입니다 (YYYY-MM-DD)")

    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == entry_date)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="해당 날짜의 일기가 없습니다")
    return entry


@router.put("/date/{date}", response_model=DiaryEntryResponse)
def update_diary_by_date(
    date: str,
    data: DiaryCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        entry_date = datetime.fromisoformat(date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 날짜 형식입니다 (YYYY-MM-DD)")

    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == entry_date)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="해당 날짜의 일기가 없습니다")

    entry.content = data.content
    entry.mood_tags = data.mood_tags
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/date/{date}")
def delete_diary_by_date(
    date: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        entry_date = datetime.fromisoformat(date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 날짜 형식입니다 (YYYY-MM-DD)")

    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == entry_date)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="해당 날짜의 일기가 없습니다")

    db.delete(entry)
    db.commit()
    return {"detail": "일기가 삭제되었습니다"}


@router.get("", response_model=list[DiaryEntryResponse])
def list_diaries(
    month: str = Query(..., description="YYYY-MM (예: 2026-02)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 해당 월의 마지막 날짜 계산
    import calendar
    start = f"{month}-01"
    year, mon = map(int, month.split('-'))
    last_day = calendar.monthrange(year, mon)[1]
    end = f"{month}-{last_day:02d}"

    entries = (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == user.id,
            DiaryEntry.entry_date >= start,
            DiaryEntry.entry_date <= end,
        )
        .order_by(DiaryEntry.entry_date.desc())
        .all()
    )
    return entries
