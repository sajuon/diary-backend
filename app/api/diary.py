from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.schemas.diary import DiaryCreateRequest, DiaryEntryResponse


router = APIRouter(prefix="/api/diary", tags=["Diary"])


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
        raise HTTPException(status_code=404, detail="오늘 작성한 일기가 없습니다")
    return entry


@router.get("", response_model=list[DiaryEntryResponse])
def list_diaries(
    month: str = Query(..., description="YYYY-MM (예: 2026-02)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 단순 구현: month prefix로 조회 (DB가 date면 between이 더 깔끔)
    start = f"{month}-01"
    end = f"{month}-31"

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
