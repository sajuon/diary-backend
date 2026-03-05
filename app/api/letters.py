from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune
from app.models.letter import OtterLetter
from app.schemas.letter import OtterLetterResponse
from app.services.letter_generator import generate_otter_letter  # async


router = APIRouter(prefix="/api/letters", tags=["Letters"])


def kst_today_date():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


@router.post("/generate/today", response_model=OtterLetterResponse)
async def generate_today_letter(
    force: bool = Query(False, description="true면 기존 편지를 삭제하고 재생성합니다"),
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
        raise HTTPException(status_code=400, detail="오늘 일기가 없습니다. 먼저 일기를 작성하세요.")

    # 이미 생성된 편지 확인
    exists = db.query(OtterLetter).filter(OtterLetter.diary_entry_id == entry.id).first()

    # force=false면 멱등 반환
    if exists and not force:
        return exists

    # force=true면 기존 편지 삭제 후 재생성
    if exists and force:
        db.delete(exists)
        db.commit()

    fortune = (
        db.query(DailyFortune)
        .filter(DailyFortune.user_id == user.id, DailyFortune.fortune_date == today)
        .first()
    )

    data = await generate_otter_letter(user=user, diary_entry=entry, fortune=fortune)

    letter = OtterLetter(
        user_id=user.id,
        diary_entry_id=entry.id,
        letter_date=today,
        content=data.get("content", ""),
        element_hint=data.get("element_hint"),
        model=data.get("model"),
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
    today = kst_today_date()

    letter = (
        db.query(OtterLetter)
        .filter(OtterLetter.user_id == user.id, OtterLetter.letter_date == today)
        .first()
    )
    if not letter:
        raise HTTPException(status_code=404, detail="오늘의 편지가 아직 없습니다")
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