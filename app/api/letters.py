from __future__ import annotations

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from calendar import monthrange

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune
from app.models.letter import OtterLetter
from app.schemas.letter import OtterLetterResponse
from app.services.letter_generator import generate_otter_letter


router = APIRouter(prefix="/api/letters", tags=["Letters"])


def kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def kst_today_date():
    return kst_now().date()


def kst_previous_day_date():
    return kst_today_date() - timedelta(days=1)


@router.get("", response_model=list[OtterLetterResponse])
def get_letters_by_month(
    month: str = Query(..., description="YYYY-MM (예: 2026-03)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        y, m = month.split("-")
        year = int(y)
        mon = int(m)
        if mon < 1 or mon > 12:
            raise ValueError
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="month 형식은 YYYY-MM 이어야 합니다. 예: 2026-03",
        )

    start_date = date(year, mon, 1)
    last_day = monthrange(year, mon)[1]
    end_date = date(year, mon, last_day)

    letters = (
        db.query(OtterLetter)
        .filter(
            OtterLetter.user_id == user.id,
            OtterLetter.letter_date >= start_date,
            OtterLetter.letter_date <= end_date,
        )
        .order_by(OtterLetter.letter_date.desc(), OtterLetter.id.desc())
        .all()
    )

    return letters


@router.get("/latest", response_model=OtterLetterResponse)
def get_latest_letter(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    letter = (
        db.query(OtterLetter)
        .filter(OtterLetter.user_id == user.id)
        .order_by(OtterLetter.letter_date.desc(), OtterLetter.id.desc())
        .first()
    )

    if not letter:
        raise HTTPException(status_code=404, detail="편지가 아직 없습니다")

    return letter


@router.post("/generate", response_model=OtterLetterResponse)
async def generate_letter_by_date(
    target_date: date | None = Query(
        default=None,
        description="생성할 대상 일기 날짜. 없으면 전날(KST) 기준으로 생성합니다. 예: 2026-03-09",
    ),
    force: bool = Query(False, description="true면 기존 편지를 삭제하고 재생성합니다"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diary_date = target_date or kst_previous_day_date()

    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == diary_date)
        .first()
    )
    if not entry:
        raise HTTPException(
            status_code=400,
            detail=f"{diary_date} 일기가 없습니다. 먼저 일기를 작성하세요.",
        )

    exists = (
        db.query(OtterLetter)
        .filter(OtterLetter.diary_entry_id == entry.id)
        .first()
    )

    if exists and not force:
        return exists

    if exists and force:
        db.delete(exists)
        db.commit()

    fortune = (
        db.query(DailyFortune)
        .filter(
            DailyFortune.user_id == user.id,
            DailyFortune.fortune_date == diary_date,
        )
        .first()
    )

    data = await generate_otter_letter(user=user, diary_entry=entry, fortune=fortune)

    letter = OtterLetter(
        user_id=user.id,
        diary_entry_id=entry.id,
        letter_date=diary_date,
        content=data.get("content", ""),
        element_hint=data.get("element_hint"),
        model=data.get("model"),
        is_read=False,
        read_at=None,
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    return letter


@router.get("/today", response_model=OtterLetterResponse)
def get_today_letter(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    호환용 엔드포인트.
    현재 정책상 자정에 전날 편지가 생성되므로,
    '오늘의 편지' 대신 가장 최근 편지를 반환합니다.
    """
    letter = (
        db.query(OtterLetter)
        .filter(OtterLetter.user_id == user.id)
        .order_by(OtterLetter.letter_date.desc(), OtterLetter.id.desc())
        .first()
    )
    if not letter:
        raise HTTPException(status_code=404, detail="편지가 아직 없습니다")
    return letter


@router.get("/{letter_id}", response_model=OtterLetterResponse)
def get_letter_by_id(
    letter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    letter = (
        db.query(OtterLetter)
        .filter(OtterLetter.id == letter_id, OtterLetter.user_id == user.id)
        .first()
    )
    if not letter:
        raise HTTPException(status_code=404, detail="편지를 찾을 수 없습니다")
    return letter


@router.patch("/{letter_id}/read", response_model=OtterLetterResponse)
def mark_letter_as_read(
    letter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    letter = (
        db.query(OtterLetter)
        .filter(OtterLetter.id == letter_id, OtterLetter.user_id == user.id)
        .first()
    )
    if not letter:
        raise HTTPException(status_code=404, detail="편지를 찾을 수 없습니다")

    if not letter.is_read:
        letter.is_read = True
        letter.read_at = kst_now()
        db.commit()
        db.refresh(letter)

    return letter