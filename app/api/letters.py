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
from app.schemas.letter import (
    OtterLetterResponse,
    OtterLetterFavoriteUpdateRequest,
)
from app.services.letter_generator import generate_otter_letter


router = APIRouter(prefix="/api/letters", tags=["Letters"])

LETTER_PEARL_COST = 1


def kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def kst_today_date():
    return kst_now().date()


def kst_previous_day_date():
    return kst_today_date() - timedelta(days=1)


def get_free_diary_entry_or_404(
    db: Session,
    user_id: int,
    target_date: date,
) -> DiaryEntry:
    entry = (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == user_id,
            DiaryEntry.entry_date == target_date,
            DiaryEntry.diary_type == "free",
        )
        .first()
    )

    if not entry:
        raise HTTPException(
            status_code=400,
            detail=f"{target_date} 자유형 일기가 없습니다. 먼저 자유형 일기를 작성하세요.",
        )

    return entry


def create_letter_for_entry(
    db: Session,
    user: User,
    entry: DiaryEntry,
    content: str,
    element_hint=None,
    model: str | None = None,
) -> OtterLetter:
    if entry.diary_type != "free":
        raise HTTPException(
            status_code=403,
            detail="질문형 일기에는 해도리 답장을 받을 수 없습니다.",
        )

    letter = OtterLetter(
        user_id=user.id,
        diary_entry_id=entry.id,
        letter_date=entry.entry_date,
        content=content,
        element_hint=element_hint,
        model=model,
        is_read=False,
        read_at=None,
    )

    db.add(letter)
    db.commit()
    db.refresh(letter)

    return letter


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
        .join(DiaryEntry, OtterLetter.diary_entry_id == DiaryEntry.id)
        .filter(
            OtterLetter.user_id == user.id,
            OtterLetter.letter_date >= start_date,
            OtterLetter.letter_date <= end_date,
            DiaryEntry.diary_type == "free",
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
        .join(DiaryEntry, OtterLetter.diary_entry_id == DiaryEntry.id)
        .filter(
            OtterLetter.user_id == user.id,
            DiaryEntry.diary_type == "free",
        )
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
        description="생성할 대상 자유형 일기 날짜. 없으면 전날(KST) 기준으로 생성합니다.",
    ),
    force: bool = Query(False, description="true면 기존 편지를 삭제하고 재생성합니다"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diary_date = target_date or kst_previous_day_date()

    entry = get_free_diary_entry_or_404(
        db=db,
        user_id=user.id,
        target_date=diary_date,
    )

    exists = db.query(OtterLetter).filter(OtterLetter.diary_entry_id == entry.id).first()

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

    return create_letter_for_entry(
        db=db,
        user=user,
        entry=entry,
        content=data.get("content", ""),
        element_hint=data.get("element_hint"),
        model=data.get("model"),
    )


@router.post("/generate-with-pearl", response_model=OtterLetterResponse)
async def generate_letter_with_pearl(
    target_date: date = Query(
        ...,
        description="진주를 사용해 답장을 받을 자유형 일기 날짜. 예: 2026-05-10",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today_date()

    if target_date > today:
        raise HTTPException(
            status_code=403,
            detail="미래 날짜의 일기에는 답장을 받을 수 없습니다.",
        )

    entry = get_free_diary_entry_or_404(
        db=db,
        user_id=user.id,
        target_date=target_date,
    )

    exists = db.query(OtterLetter).filter(OtterLetter.diary_entry_id == entry.id).first()

    if exists:
        return exists

    if user.pearls < LETTER_PEARL_COST:
        raise HTTPException(
            status_code=400,
            detail=f"진주가 부족합니다. 답장을 받으려면 진주 {LETTER_PEARL_COST}개가 필요합니다.",
        )

    fortune = (
        db.query(DailyFortune)
        .filter(
            DailyFortune.user_id == user.id,
            DailyFortune.fortune_date == target_date,
        )
        .first()
    )

    data = await generate_otter_letter(user=user, diary_entry=entry, fortune=fortune)

    user.pearls -= LETTER_PEARL_COST

    letter = OtterLetter(
        user_id=user.id,
        diary_entry_id=entry.id,
        letter_date=target_date,
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
    letter = (
        db.query(OtterLetter)
        .join(DiaryEntry, OtterLetter.diary_entry_id == DiaryEntry.id)
        .filter(
            OtterLetter.user_id == user.id,
            DiaryEntry.diary_type == "free",
        )
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
        .join(DiaryEntry, OtterLetter.diary_entry_id == DiaryEntry.id)
        .filter(
            OtterLetter.id == letter_id,
            OtterLetter.user_id == user.id,
            DiaryEntry.diary_type == "free",
        )
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
        .join(DiaryEntry, OtterLetter.diary_entry_id == DiaryEntry.id)
        .filter(
            OtterLetter.id == letter_id,
            OtterLetter.user_id == user.id,
            DiaryEntry.diary_type == "free",
        )
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


@router.patch("/{letter_id}/favorite", response_model=OtterLetterResponse)
def update_letter_favorite(
    letter_id: int,
    payload: OtterLetterFavoriteUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    letter = (
        db.query(OtterLetter)
        .join(DiaryEntry, OtterLetter.diary_entry_id == DiaryEntry.id)
        .filter(
            OtterLetter.id == letter_id,
            OtterLetter.user_id == user.id,
            DiaryEntry.diary_type == "free",
        )
        .first()
    )

    if not letter:
        raise HTTPException(status_code=404, detail="편지를 찾을 수 없습니다")

    letter.is_favorite = payload.is_favorite
    db.commit()
    db.refresh(letter)

    return letter