# /home/dori/diary-backend/app/api/letters.py
# 역할: 자유형 일기에 대한 해도리 답장 조회/생성 API
# 규칙: 전날 일기 답장은 마감 시각(=배치 시각, 기본 03시) 배치가 그 시점 최종 저장본으로 생성.
#       답장이 없는 지난 일기는 진주 1개로 즉시 생성.
#       답장이 있는 지난 일기는 진주 3개로 재생성 (기존 답장·즐겨찾기·피드백 삭제).
#       답장은 일기당 1개 (uq_letter_diary_entry_id).
#       진주 차감·답장 저장은 사용자 행 잠금(SELECT ... FOR UPDATE) 안에서 한 트랜잭션으로 처리하고,
#       LLM 호출은 잠금 밖에서 먼저 한다. LLM 실패 시 아무것도 바뀌지 않는다.

from __future__ import annotations

from datetime import datetime, date
from zoneinfo import ZoneInfo
from calendar import monthrange

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune
from app.models.letter import OtterLetter
from app.schemas.letter import (
    OtterLetterResponse,
    OtterLetterFavoriteUpdateRequest,
    LetterRegenerateInfo,
)
from app.models.pearl import PearlTransaction
from app.services.letter_generator import generate_otter_letter
from app.services.diary_day import grace_previous_day
from app.models.letter_feedback import LetterFeedback
from app.schemas.pearl import LetterFeedbackRequest, LetterFeedbackResponse
from app.services.pearls import REWARD_LETTER_FEEDBACK, award_reward


router = APIRouter(prefix="/api/letters", tags=["Letters"])

logger = logging.getLogger(__name__)

LETTER_PEARL_COST = 1
LETTER_REGENERATE_PEARL_COST = 3


def kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def kst_today_date():
    return kst_now().date()


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


def _validate_past_date(target_date: date) -> None:
    today = kst_today_date()

    if target_date > today:
        raise HTTPException(
            status_code=403,
            detail="미래 날짜의 일기에는 답장을 받을 수 없습니다.",
        )

    if target_date == today or target_date == grace_previous_day():
        # 마감 전(자정~배치 시각)의 전날 일기는 곧 배치가 무료로 답장을 만든다
        raise HTTPException(
            status_code=400,
            detail="이 일기의 답장은 새벽에 도착해요.",
        )


def _get_letter_for_entry(db: Session, entry_id: int) -> OtterLetter | None:
    return db.query(OtterLetter).filter(OtterLetter.diary_entry_id == entry_id).first()


def _diary_modified_since(entry: DiaryEntry, letter: OtterLetter) -> bool:
    if entry.updated_at is None or letter.created_at is None:
        return False
    return entry.updated_at > letter.created_at


def _not_enough_pearls(cost: int, action: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=f"진주가 부족합니다. {action} 진주 {cost}개가 필요합니다.",
    )


async def _generate_letter_data(user: User, entry: DiaryEntry, db: Session) -> dict:
    fortune = (
        db.query(DailyFortune)
        .filter(
            DailyFortune.user_id == user.id,
            DailyFortune.fortune_date == entry.entry_date,
        )
        .first()
    )
    try:
        return await generate_otter_letter(user=user, diary_entry=entry, fortune=fortune)
    except HTTPException:
        raise
    except Exception:
        logger.exception("[LETTER] LLM generation failed entry_id=%s", entry.id)
        raise HTTPException(
            status_code=502,
            detail="답장을 만들지 못했어요. 진주는 차감되지 않았어요. 잠시 후 다시 시도해주세요.",
        )


def _lock_user_and_charge(db: Session, user_id: int, cost: int, reason: str, ref_key: str | None) -> bool:
    """
    사용자 행을 잠그고 진주를 차감한다. 잔액 부족이면 False (호출 쪽에서 rollback).
    커밋은 호출 쪽에서 답장 저장과 함께 한다.
    """
    db.query(User).filter(User.id == user_id).with_for_update().one()
    deducted = (
        db.query(User)
        .filter(User.id == user_id, User.pearls >= cost)
        .update({User.pearls: User.pearls - cost}, synchronize_session=False)
    )
    if not deducted:
        return False
    balance = db.query(User.pearls).filter(User.id == user_id).scalar()
    db.add(
        PearlTransaction(
            user_id=user_id,
            amount=-cost,
            reason=reason,
            ref_key=ref_key,
            balance_after=int(balance or 0),
        )
    )
    return True


def _new_letter(user_id: int, entry: DiaryEntry, data: dict) -> OtterLetter:
    return OtterLetter(
        user_id=user_id,
        diary_entry_id=entry.id,
        letter_date=entry.entry_date,
        content=data.get("content", ""),
        element_hint=data.get("element_hint"),
        model=data.get("model"),
        is_read=False,
        read_at=None,
    )


@router.post("/generate-with-pearl", response_model=OtterLetterResponse)
async def generate_letter_with_pearl(
    target_date: date = Query(
        ...,
        description="답장을 받을 지난 자유형 일기 날짜. 진주 1개를 사용합니다. 예: 2026-05-10",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_past_date(target_date)

    entry = get_free_diary_entry_or_404(db=db, user_id=user.id, target_date=target_date)

    exists = _get_letter_for_entry(db, entry.id)
    if exists:
        return exists

    # LLM 호출 전 잔액 확인 (실제 차감은 잠금 안에서 다시 확인)
    if user.pearls < LETTER_PEARL_COST:
        raise _not_enough_pearls(LETTER_PEARL_COST, "답장을 받으려면")

    data = await _generate_letter_data(user, entry, db)

    # LLM 호출 동안 열린 읽기 트랜잭션을 정리하고 최신 상태 기준으로 잠근다.
    db.rollback()
    try:
        if not _lock_user_and_charge(db, user.id, LETTER_PEARL_COST, "letter_cost", None):
            db.rollback()
            raise _not_enough_pearls(LETTER_PEARL_COST, "답장을 받으려면")

        # 잠금 안에서 다시 확인: 동시에 들어온 요청이 먼저 만들었으면 차감 없이 그 답장을 반환
        exists = _get_letter_for_entry(db, entry.id)
        if exists:
            db.rollback()
            return _get_letter_for_entry(db, entry.id)

        letter = _new_letter(user.id, entry, data)
        db.add(letter)
        db.commit()
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        exists = _get_letter_for_entry(db, entry.id)
        if exists:
            return exists
        raise HTTPException(status_code=409, detail="답장 저장 중 충돌이 발생했어요. 다시 시도해주세요.")
    except Exception:
        db.rollback()
        logger.exception("[LETTER] save failed entry_id=%s", entry.id)
        raise HTTPException(status_code=500, detail="답장 저장에 실패했어요. 진주는 차감되지 않았어요.")

    db.refresh(letter)
    return letter


@router.get("/regenerate-info", response_model=LetterRegenerateInfo)
def get_regenerate_info(
    target_date: date = Query(..., description="재생성할 지난 자유형 일기 날짜. 예: 2026-05-10"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """재생성 안내 모달용. 일기 수정 여부와 비용·잔액을 돌려준다."""
    _validate_past_date(target_date)
    entry = get_free_diary_entry_or_404(db=db, user_id=user.id, target_date=target_date)
    letter = _get_letter_for_entry(db, entry.id)
    if not letter:
        raise HTTPException(status_code=404, detail="이 일기에는 아직 답장이 없어요.")

    return LetterRegenerateInfo(
        letter_id=letter.id,
        diary_entry_id=entry.id,
        letter_date=letter.letter_date,
        diary_modified=_diary_modified_since(entry, letter),
        cost=LETTER_REGENERATE_PEARL_COST,
        pearls=int(user.pearls or 0),
    )


@router.post("/regenerate", response_model=OtterLetterResponse)
async def regenerate_letter(
    target_date: date = Query(..., description="재생성할 지난 자유형 일기 날짜. 진주 3개를 사용합니다."),
    letter_id: int = Query(..., description="교체할 기존 답장 ID (regenerate-info의 letter_id)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    기존 답장을 삭제하고 현재 일기 내용으로 새 답장을 만든다 (진주 3개).
    - 기존 답장의 즐겨찾기·피드백도 함께 삭제된다.
    - 피드백 보상은 일기당 1번이라 새 답장에 피드백해도 다시 지급되지 않는다.
    - LLM 실패·저장 실패 시 진주 차감과 삭제 모두 일어나지 않는다.
    - letter_id가 현재 답장과 다르면(이미 다른 요청이 교체함) 409, 차감 없음.
    """
    _validate_past_date(target_date)
    entry = get_free_diary_entry_or_404(db=db, user_id=user.id, target_date=target_date)

    current = _get_letter_for_entry(db, entry.id)
    if not current:
        raise HTTPException(status_code=404, detail="이 일기에는 아직 답장이 없어요.")
    if current.id != letter_id:
        raise HTTPException(status_code=409, detail="이미 새 답장으로 바뀌었어요. 화면을 새로고침해주세요.")

    if user.pearls < LETTER_REGENERATE_PEARL_COST:
        raise _not_enough_pearls(LETTER_REGENERATE_PEARL_COST, "답장을 다시 받으려면")

    data = await _generate_letter_data(user, entry, db)

    db.rollback()
    try:
        if not _lock_user_and_charge(
            db, user.id, LETTER_REGENERATE_PEARL_COST, "letter_regenerate_cost", None
        ):
            db.rollback()
            raise _not_enough_pearls(LETTER_REGENERATE_PEARL_COST, "답장을 다시 받으려면")

        # 잠금 안에서 다시 확인: 연타·동시 요청이면 두 번째 요청은 여기서 걸러진다
        current = (
            db.query(OtterLetter)
            .filter(OtterLetter.diary_entry_id == entry.id)
            .with_for_update()
            .first()
        )
        if not current or current.id != letter_id:
            db.rollback()
            raise HTTPException(status_code=409, detail="이미 새 답장으로 바뀌었어요. 화면을 새로고침해주세요.")

        old_id = current.id
        # letter_feedback은 FK ON DELETE CASCADE로 함께 삭제
        db.query(LetterFeedback).filter(LetterFeedback.letter_id == old_id).delete(
            synchronize_session=False
        )
        db.delete(current)
        db.flush()

        letter = _new_letter(user.id, entry, data)
        db.add(letter)
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("[LETTER] regenerate save failed entry_id=%s", entry.id)
        raise HTTPException(
            status_code=500,
            detail="답장을 바꾸지 못했어요. 기존 답장과 진주는 그대로예요.",
        )

    db.refresh(letter)
    logger.info(
        "[LETTER] regenerated entry_id=%s old_letter_id=%s new_letter_id=%s user_id=%s",
        entry.id,
        old_id,
        letter.id,
        user.id,
    )
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


def _get_own_letter(db: Session, user_id: int, letter_id: int) -> OtterLetter:
    letter = (
        db.query(OtterLetter)
        .filter(OtterLetter.id == letter_id, OtterLetter.user_id == user_id)
        .first()
    )
    if not letter:
        raise HTTPException(status_code=404, detail="편지를 찾을 수 없습니다")
    return letter


@router.get("/{letter_id}/feedback", response_model=LetterFeedbackResponse | None)
def get_letter_feedback(
    letter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_own_letter(db, user.id, letter_id)
    return (
        db.query(LetterFeedback)
        .filter(LetterFeedback.letter_id == letter_id, LetterFeedback.user_id == user.id)
        .first()
    )


@router.post("/{letter_id}/feedback", response_model=LetterFeedbackResponse)
def send_letter_feedback(
    letter_id: int,
    payload: LetterFeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    편지 피드백 저장 (좋아요/아쉬워요 + 한마디).
    진주 +2는 일기당 1번 (ref_key = entry:<diary_entry_id>).
    답장을 재생성해 새 답장에 피드백해도 다시 지급하지 않는다.
    """
    letter = _get_own_letter(db, user.id, letter_id)

    comment = (payload.comment or "").strip()
    if not comment:
        raise HTTPException(status_code=400, detail="한마디를 적어주세요")

    feedback = (
        db.query(LetterFeedback)
        .filter(LetterFeedback.letter_id == letter_id, LetterFeedback.user_id == user.id)
        .first()
    )
    if feedback:
        feedback.rating = payload.rating
        feedback.comment = comment
    else:
        feedback = LetterFeedback(
            letter_id=letter_id,
            user_id=user.id,
            rating=payload.rating,
            comment=comment,
        )
        db.add(feedback)

    db.commit()

    reward = award_reward(
        db, user.id, REWARD_LETTER_FEEDBACK, f"entry:{letter.diary_entry_id}"
    )
    db.refresh(feedback)
    feedback.pearl_reward = reward
    return feedback

