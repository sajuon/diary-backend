# /home/dori/diary-backend/app/api/diary.py

from datetime import datetime, date
from zoneinfo import ZoneInfo
import calendar
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.schemas.diary import DiaryCreateRequest, DiaryEntryResponse
from app.schemas.diary_question import DiaryQuestionResponse
from app.services.question_llm_service import get_or_create_today_question
from app.services.letter_llm_service import LetterLLMError
from app.services.diary_tag_service import generate_summary_tag

router = APIRouter(prefix="/api/diary", tags=["Diary"])
logger = logging.getLogger(__name__)


class QuestionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    entry_date: date
    content: str
    weather: str | None = None
    mood_tags: list[str] | None = None
    summary_tag: str | None = None
    diary_type: str | None = None
    question_id: str | None = None
    question_text: str | None = None
    created_at: datetime
    updated_at: datetime


class QuestionHistoryResponse(BaseModel):
    month_day: str | None = None
    question_id: str | None = None
    question_text: str | None = None
    items: list[QuestionHistoryItem]


def kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def kst_today_date():
    return kst_now().date()


def is_before_11pm_kst():
    return kst_now().hour < 23


def parse_date_string(date: str):
    try:
        return datetime.fromisoformat(date).date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="잘못된 날짜 형식입니다 (YYYY-MM-DD)",
        )


def parse_month_day_string(month_day: str) -> tuple[int, int]:
    try:
        month_str, day_str = month_day.split("-")
        month = int(month_str)
        day = int(day_str)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="month_day 형식은 MM-DD 이어야 합니다. 예: 05-12",
        )

    if month < 1 or month > 12 or day < 1 or day > 31:
        raise HTTPException(
            status_code=400,
            detail="month_day 값이 올바르지 않습니다.",
        )

    return month, day


def parse_month_string(month: str) -> tuple[int, int]:
    try:
        year, mon = map(int, month.split("-"))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="잘못된 month 형식입니다 (YYYY-MM)",
        )

    if mon < 1 or mon > 12:
        raise HTTPException(
            status_code=400,
            detail="month의 월 값이 올바르지 않습니다",
        )

    return year, mon


def normalize_diary_type(diary_type: str | None) -> str:
    if diary_type in ("question", "free"):
        return diary_type
    return "free"


def normalize_question_id(diary_type: str, question_id: str | None) -> str | None:
    if diary_type != "question":
        return None

    if question_id is None:
        return None

    cleaned = question_id.strip()
    return cleaned or None


def normalize_question_text(diary_type: str, question_text: str | None) -> str | None:
    if diary_type != "question":
        return None

    if question_text is None:
        return None

    cleaned = question_text.strip()
    return cleaned or None


def get_month_day_from_date(entry_date: date) -> str:
    return f"{entry_date.month:02d}-{entry_date.day:02d}"


def get_requested_entry_date(data: DiaryCreateRequest):
    today = kst_today_date()
    raw_entry_date = getattr(data, "entry_date", None)

    if raw_entry_date:
        entry_date = parse_date_string(str(raw_entry_date))
    else:
        entry_date = today

    if entry_date > today:
        raise HTTPException(
            status_code=403,
            detail="미래 날짜의 일기는 미리 작성할 수 없습니다",
        )

    return entry_date


def get_diary_entry_or_404(
    db: Session,
    user_id: int,
    entry_date,
    diary_type: str,
) -> DiaryEntry:
    entry = (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == user_id,
            DiaryEntry.entry_date == entry_date,
            DiaryEntry.diary_type == diary_type,
        )
        .first()
    )

    if not entry:
        type_label = "질문형" if diary_type == "question" else "자유형"
        raise HTTPException(
            status_code=404,
            detail=f"해당 날짜의 {type_label} 일기가 없습니다",
        )

    return entry


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


@router.get("/question-history", response_model=QuestionHistoryResponse)
def get_question_history(
    month_day: str = Query(..., description="MM-DD 형식. 예: 05-13"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    month, day = parse_month_day_string(month_day)

    entries = (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == user.id,
            DiaryEntry.diary_type == "question",
            func.month(DiaryEntry.entry_date) == month,
            func.day(DiaryEntry.entry_date) == day,
        )
        .order_by(DiaryEntry.entry_date.desc(), DiaryEntry.id.desc())
        .all()
    )

    question_text = None
    for entry in entries:
        if entry.question_text:
            question_text = entry.question_text
            break

    return {
        "month_day": month_day,
        "question_id": month_day,
        "question_text": question_text,
        "items": entries,
    }


@router.get("/today", response_model=DiaryEntryResponse)
def get_today_diary(
    diary_type: str = Query(default="free", description="question 또는 free"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today_date()
    normalized_type = normalize_diary_type(diary_type)

    return get_diary_entry_or_404(
        db=db,
        user_id=user.id,
        entry_date=today,
        diary_type=normalized_type,
    )


@router.post("/today", response_model=DiaryEntryResponse)
async def create_today_diary(
    data: DiaryCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry_date = get_requested_entry_date(data)
    diary_type = normalize_diary_type(data.diary_type)
    question_id = normalize_question_id(
        diary_type,
        data.question_id or get_month_day_from_date(entry_date),
    )
    question_text = normalize_question_text(diary_type, data.question_text)

    exists = (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == user.id,
            DiaryEntry.entry_date == entry_date,
            DiaryEntry.diary_type == diary_type,
        )
        .first()
    )

    if exists:
        type_label = "질문형" if diary_type == "question" else "자유형"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"해당 날짜의 {type_label} 일기는 이미 작성했습니다",
        )

    logger.info(
        "[DIARY_CREATE] start user_id=%s entry_date=%s diary_type=%s question_id=%s content_len=%s",
        user.id,
        str(entry_date),
        diary_type,
        question_id,
        len(data.content or ""),
    )

    summary_tag = None
    if diary_type == "free":
        summary_tag = await generate_summary_tag(data.content)

    entry = DiaryEntry(
        user_id=user.id,
        entry_date=entry_date,
        content=data.content,
        weather=data.weather,
        mood_tags=data.mood_tags,
        summary_tag=summary_tag,
        diary_type=diary_type,
        question_id=question_id,
        question_text=question_text,
    )

    db.add(entry)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        type_label = "질문형" if diary_type == "question" else "자유형"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"해당 날짜의 {type_label} 일기는 이미 작성했습니다",
        )

    db.refresh(entry)

    logger.info(
        "[DIARY_CREATE] saved entry_id=%s user_id=%s entry_date=%s diary_type=%s question_id=%s summary_tag=%s",
        entry.id,
        user.id,
        str(entry.entry_date),
        entry.diary_type,
        entry.question_id,
        entry.summary_tag,
    )

    return entry


@router.put("/today", response_model=DiaryEntryResponse)
async def update_today_diary(
    data: DiaryCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today_date()
    diary_type = normalize_diary_type(data.diary_type)

    entry = get_diary_entry_or_404(
        db=db,
        user_id=user.id,
        entry_date=today,
        diary_type=diary_type,
    )

    if not is_before_11pm_kst():
        raise HTTPException(
            status_code=403,
            detail="오늘 일기는 오후 11시까지만 수정할 수 있습니다",
        )

    question_id = normalize_question_id(
        diary_type,
        data.question_id or entry.question_id or get_month_day_from_date(today),
    )
    question_text = normalize_question_text(diary_type, data.question_text)

    logger.info(
        "[DIARY_UPDATE_TODAY] start entry_id=%s user_id=%s today=%s diary_type=%s question_id=%s content_len=%s old_tag=%s",
        entry.id,
        user.id,
        str(today),
        diary_type,
        question_id,
        len(data.content or ""),
        entry.summary_tag,
    )

    entry.content = data.content
    entry.weather = data.weather
    entry.mood_tags = data.mood_tags
    entry.diary_type = diary_type
    entry.question_id = question_id
    entry.question_text = question_text

    if diary_type == "free":
        entry.summary_tag = await generate_summary_tag(data.content)
    else:
        entry.summary_tag = None

    db.commit()
    db.refresh(entry)

    return entry


@router.get("/date/{date}", response_model=DiaryEntryResponse)
def get_diary_by_date(
    date: str,
    diary_type: str = Query(default="free", description="question 또는 free"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry_date = parse_date_string(date)
    normalized_type = normalize_diary_type(diary_type)

    return get_diary_entry_or_404(
        db=db,
        user_id=user.id,
        entry_date=entry_date,
        diary_type=normalized_type,
    )


@router.put("/date/{date}", response_model=DiaryEntryResponse)
async def update_diary_by_date(
    date: str,
    data: DiaryCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry_date = parse_date_string(date)
    today = kst_today_date()
    diary_type = normalize_diary_type(data.diary_type)

    if entry_date > today:
        raise HTTPException(
            status_code=403,
            detail="미래 날짜의 일기는 수정할 수 없습니다",
        )

    if entry_date == today and not is_before_11pm_kst():
        raise HTTPException(
            status_code=403,
            detail="오늘 일기는 오후 11시까지만 수정할 수 있습니다",
        )

    entry = get_diary_entry_or_404(
        db=db,
        user_id=user.id,
        entry_date=entry_date,
        diary_type=diary_type,
    )

    question_id = normalize_question_id(
        diary_type,
        data.question_id or entry.question_id or get_month_day_from_date(entry_date),
    )
    question_text = normalize_question_text(diary_type, data.question_text)

    logger.info(
        "[DIARY_UPDATE_BY_DATE] start entry_id=%s user_id=%s entry_date=%s diary_type=%s question_id=%s content_len=%s old_tag=%s",
        entry.id,
        user.id,
        str(entry_date),
        diary_type,
        question_id,
        len(data.content or ""),
        entry.summary_tag,
    )

    entry.content = data.content
    entry.weather = data.weather
    entry.mood_tags = data.mood_tags
    entry.diary_type = diary_type
    entry.question_id = question_id
    entry.question_text = question_text

    if diary_type == "free":
        entry.summary_tag = await generate_summary_tag(data.content)
    else:
        entry.summary_tag = None

    db.commit()
    db.refresh(entry)

    logger.info(
        "[DIARY_UPDATE_BY_DATE] saved entry_id=%s user_id=%s diary_type=%s question_id=%s summary_tag=%s",
        entry.id,
        user.id,
        entry.diary_type,
        entry.question_id,
        entry.summary_tag,
    )

    return entry


@router.delete("/date/{date}")
def delete_diary_by_date(
    date: str,
    diary_type: str = Query(default="free", description="question 또는 free"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry_date = parse_date_string(date)
    normalized_type = normalize_diary_type(diary_type)

    entry = get_diary_entry_or_404(
        db=db,
        user_id=user.id,
        entry_date=entry_date,
        diary_type=normalized_type,
    )

    logger.info(
        "[DIARY_DELETE] deleting entry_id=%s user_id=%s entry_date=%s diary_type=%s",
        entry.id,
        user.id,
        str(entry_date),
        entry.diary_type,
    )

    db.delete(entry)
    db.commit()

    return {"detail": "일기가 삭제되었습니다"}


@router.get("", response_model=list[DiaryEntryResponse])
def list_diaries(
    month: str = Query(..., description="YYYY-MM (예: 2026-02)"),
    diary_type: str | None = Query(
        default=None,
        description="선택값. question 또는 free. 없으면 전체",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, mon = parse_month_string(month)
    last_day = calendar.monthrange(year, mon)[1]

    start = f"{month}-01"
    end = f"{month}-{last_day:02d}"

    query = db.query(DiaryEntry).filter(
        DiaryEntry.user_id == user.id,
        DiaryEntry.entry_date >= start,
        DiaryEntry.entry_date <= end,
    )

    if diary_type:
        query = query.filter(DiaryEntry.diary_type == normalize_diary_type(diary_type))

    entries = query.order_by(DiaryEntry.entry_date.desc(), DiaryEntry.id.desc()).all()

    return entries


@router.post("/summary-tag/batch-missing")
async def generate_missing_summary_tags(
    month: str | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=1000),
    force: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started_at = kst_now()

    try:
        base_query = db.query(DiaryEntry).filter(
            DiaryEntry.user_id == user.id,
            DiaryEntry.diary_type == "free",
        )

        if month:
            year, mon = parse_month_string(month)
            last_day = calendar.monthrange(year, mon)[1]
            start = f"{month}-01"
            end = f"{month}-{last_day:02d}"

            base_query = base_query.filter(
                DiaryEntry.entry_date >= start,
                DiaryEntry.entry_date <= end,
            )

        total_candidates_before_filter = base_query.count()

        if not force:
            base_query = base_query.filter(
                (DiaryEntry.summary_tag.is_(None)) | (DiaryEntry.summary_tag == "")
            )

        entries = base_query.order_by(DiaryEntry.entry_date.asc()).limit(limit).all()

        if not entries:
            return {
                "message": "태그 없는 자유형 일기가 없습니다.",
                "updated_count": 0,
                "items": [],
                "failed_count": 0,
                "failed_items": [],
                "month": month,
                "force": force,
                "limit": limit,
                "total_candidates_before_filter": total_candidates_before_filter,
            }

        updated_items = []
        failed_items = []

        for entry in entries:
            try:
                content = (entry.content or "").strip()

                if not content:
                    failed_items.append(
                        {
                            "id": entry.id,
                            "entry_date": str(entry.entry_date),
                            "reason": "일기 내용이 비어 있습니다.",
                        }
                    )
                    continue

                summary_tag = await generate_summary_tag(content)
                entry.summary_tag = summary_tag

                updated_items.append(
                    {
                        "id": entry.id,
                        "entry_date": str(entry.entry_date),
                        "diary_type": entry.diary_type,
                        "summary_tag": summary_tag,
                    }
                )

            except Exception as e:
                logger.exception(
                    "[SUMMARY_TAG_BATCH] failed entry_id=%s entry_date=%s error=%s",
                    entry.id,
                    str(entry.entry_date),
                    str(e),
                )
                failed_items.append(
                    {
                        "id": entry.id,
                        "entry_date": str(entry.entry_date),
                        "reason": str(e),
                    }
                )

        db.commit()

        finished_at = kst_now()
        elapsed_ms = int((finished_at - started_at).total_seconds() * 1000)

        return {
            "message": f"{len(updated_items)}개의 자유형 일기 요약 태그를 생성했습니다.",
            "updated_count": len(updated_items),
            "items": updated_items,
            "failed_count": len(failed_items),
            "failed_items": failed_items,
            "month": month,
            "force": force,
            "limit": limit,
            "total_candidates_before_filter": total_candidates_before_filter,
            "elapsed_ms": elapsed_ms,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(
            "[SUMMARY_TAG_BATCH] fatal error user_id=%s month=%s error=%s",
            user.id,
            month,
            str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"요약 태그 일괄 생성 중 오류 발생: {str(e)}",
        )