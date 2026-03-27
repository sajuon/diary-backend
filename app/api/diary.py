from datetime import datetime
from zoneinfo import ZoneInfo
import calendar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.schemas.diary import DiaryCreateRequest, DiaryEntryResponse
from app.schemas.diary_question import DiaryQuestionResponse
from app.services.question_llm_service import get_or_create_today_question
from app.services.letter_llm_service import LetterLLMError

router = APIRouter(prefix="/api/diary", tags=["Diary"])


def kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def kst_today_date():
    return kst_now().date()


def is_before_11pm_kst():
    return kst_now().hour < 23


@router.get("/question", response_model=DiaryQuestionResponse)
async def get_today_question(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return await get_or_create_today_question(db=db, user=user)
    except LetterLLMError as e:
        raise HTTPException(
            status_code=502,
            detail=str(e) or "질문 생성에 실패했습니다.",
        )


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
        weather=data.weather,
        mood_tags=data.mood_tags,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/today", response_model=DiaryEntryResponse)
def update_today_diary(
    data: DiaryCreateRequest,
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

    if not is_before_11pm_kst():
        raise HTTPException(
            status_code=403,
            detail="오늘 일기는 오후 11시까지만 수정할 수 있습니다",
        )

    entry.content = data.content
    entry.weather = data.weather
    entry.mood_tags = data.mood_tags
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
        raise HTTPException(
            status_code=400,
            detail="잘못된 날짜 형식입니다 (YYYY-MM-DD)",
        )

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
        raise HTTPException(
            status_code=400,
            detail="잘못된 날짜 형식입니다 (YYYY-MM-DD)",
        )

    today = kst_today_date()

    if entry_date != today:
        raise HTTPException(
            status_code=403,
            detail="오늘 일기만 수정할 수 있습니다",
        )

    if not is_before_11pm_kst():
        raise HTTPException(
            status_code=403,
            detail="오늘 일기는 오후 11시까지만 수정할 수 있습니다",
        )

    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == entry_date)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="해당 날짜의 일기가 없습니다")

    entry.content = data.content
    entry.weather = data.weather
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
        raise HTTPException(
            status_code=400,
            detail="잘못된 날짜 형식입니다 (YYYY-MM-DD)",
        )

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
    year, mon = map(int, month.split("-"))
    last_day = calendar.monthrange(year, mon)[1]

    start = f"{month}-01"
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