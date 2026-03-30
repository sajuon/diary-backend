from datetime import datetime
from zoneinfo import ZoneInfo
import calendar
import logging
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

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


def kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def kst_today_date():
    return kst_now().date()


def is_before_11pm_kst():
    return kst_now().hour < 23


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
async def create_today_diary(
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

    logger.info(
        "[DIARY_CREATE] start user_id=%s today=%s content_len=%s",
        user.id,
        str(today),
        len(data.content or ""),
    )

    summary_tag = await generate_summary_tag(data.content)

    logger.info(
        "[DIARY_CREATE] generated summary_tag user_id=%s today=%s summary_tag=%s",
        user.id,
        str(today),
        summary_tag,
    )

    entry = DiaryEntry(
        user_id=user.id,
        entry_date=today,
        content=data.content,
        weather=data.weather,
        mood_tags=data.mood_tags,
        summary_tag=summary_tag,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info(
        "[DIARY_CREATE] saved entry_id=%s user_id=%s summary_tag=%s",
        entry.id,
        user.id,
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

    logger.info(
        "[DIARY_UPDATE_TODAY] start entry_id=%s user_id=%s today=%s content_len=%s old_tag=%s",
        entry.id,
        user.id,
        str(today),
        len(data.content or ""),
        entry.summary_tag,
    )

    entry.content = data.content
    entry.weather = data.weather
    entry.mood_tags = data.mood_tags
    entry.summary_tag = await generate_summary_tag(data.content)

    logger.info(
        "[DIARY_UPDATE_TODAY] generated summary_tag entry_id=%s user_id=%s new_tag=%s",
        entry.id,
        user.id,
        entry.summary_tag,
    )

    db.commit()
    db.refresh(entry)

    logger.info(
        "[DIARY_UPDATE_TODAY] saved entry_id=%s user_id=%s summary_tag=%s",
        entry.id,
        user.id,
        entry.summary_tag,
    )

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
async def update_diary_by_date(
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

    logger.info(
        "[DIARY_UPDATE_BY_DATE] start entry_id=%s user_id=%s entry_date=%s content_len=%s old_tag=%s",
        entry.id,
        user.id,
        str(entry_date),
        len(data.content or ""),
        entry.summary_tag,
    )

    entry.content = data.content
    entry.weather = data.weather
    entry.mood_tags = data.mood_tags
    entry.summary_tag = await generate_summary_tag(data.content)

    logger.info(
        "[DIARY_UPDATE_BY_DATE] generated summary_tag entry_id=%s user_id=%s new_tag=%s",
        entry.id,
        user.id,
        entry.summary_tag,
    )

    db.commit()
    db.refresh(entry)

    logger.info(
        "[DIARY_UPDATE_BY_DATE] saved entry_id=%s user_id=%s summary_tag=%s",
        entry.id,
        user.id,
        entry.summary_tag,
    )

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

    logger.info(
        "[DIARY_DELETE] deleting entry_id=%s user_id=%s entry_date=%s",
        entry.id,
        user.id,
        str(entry_date),
    )

    db.delete(entry)
    db.commit()
    return {"detail": "일기가 삭제되었습니다"}


@router.get("", response_model=list[DiaryEntryResponse])
def list_diaries(
    month: str = Query(..., description="YYYY-MM (예: 2026-02)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, mon = parse_month_string(month)
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


@router.post("/summary-tag/batch-missing")
async def generate_missing_summary_tags(
    month: str | None = Query(
        default=None,
        description="선택값. YYYY-MM 형식으로 특정 월만 처리",
    ),
    limit: int = Query(
        default=300,
        ge=1,
        le=1000,
        description="최대 처리 개수",
    ),
    force: bool = Query(
        default=False,
        description="true면 기존 태그가 있어도 다시 생성",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started_at = kst_now()

    logger.info(
        "[SUMMARY_TAG_BATCH] start user_id=%s month=%s limit=%s force=%s at=%s",
        user.id,
        month,
        limit,
        force,
        started_at.isoformat(),
    )

    try:
        base_query = db.query(DiaryEntry).filter(DiaryEntry.user_id == user.id)

        if month:
            year, mon = parse_month_string(month)
            last_day = calendar.monthrange(year, mon)[1]
            start = f"{month}-01"
            end = f"{month}-{last_day:02d}"

            base_query = base_query.filter(
                DiaryEntry.entry_date >= start,
                DiaryEntry.entry_date <= end,
            )

            logger.info(
                "[SUMMARY_TAG_BATCH] applied month filter user_id=%s month=%s start=%s end=%s",
                user.id,
                month,
                start,
                end,
            )

        total_candidates_before_filter = base_query.count()

        if not force:
            base_query = base_query.filter(
                (DiaryEntry.summary_tag.is_(None)) | (DiaryEntry.summary_tag == "")
            )

        entries = (
            base_query.order_by(DiaryEntry.entry_date.asc())
            .limit(limit)
            .all()
        )

        logger.info(
            "[SUMMARY_TAG_BATCH] selected entries user_id=%s total_candidates_before_filter=%s selected_count=%s",
            user.id,
            total_candidates_before_filter,
            len(entries),
        )

        if not entries:
            logger.warning(
                "[SUMMARY_TAG_BATCH] no entries to process user_id=%s month=%s force=%s",
                user.id,
                month,
                force,
            )
            return {
                "message": "태그 없는 일기가 없습니다.",
                "updated_count": 0,
                "items": [],
                "failed_count": 0,
                "failed_items": [],
                "month": month,
                "force": force,
                "limit": limit,
            }

        updated_items = []
        failed_items = []

        for entry in entries:
            try:
                content = (entry.content or "").strip()

                logger.info(
                    "[SUMMARY_TAG_BATCH] processing entry_id=%s entry_date=%s content_len=%s old_tag=%s",
                    entry.id,
                    str(entry.entry_date),
                    len(content),
                    entry.summary_tag,
                )

                if not content:
                    logger.warning(
                        "[SUMMARY_TAG_BATCH] skipped empty content entry_id=%s entry_date=%s",
                        entry.id,
                        str(entry.entry_date),
                    )
                    failed_items.append(
                        {
                            "id": entry.id,
                            "entry_date": str(entry.entry_date),
                            "reason": "일기 내용이 비어 있습니다.",
                        }
                    )
                    continue

                logger.info(
                    "[SUMMARY_TAG_BATCH] tag generation start entry_id=%s preview=%s",
                    entry.id,
                    content[:120].replace("\n", " "),
                )

                summary_tag = await generate_summary_tag(content)

                logger.info(
                    "[SUMMARY_TAG_BATCH] tag generation done entry_id=%s generated_tag=%s",
                    entry.id,
                    summary_tag,
                )

                entry.summary_tag = summary_tag

                updated_items.append(
                    {
                        "id": entry.id,
                        "entry_date": str(entry.entry_date),
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

        logger.info(
            "[SUMMARY_TAG_BATCH] pre-commit user_id=%s updated_count=%s failed_count=%s updated_ids=%s",
            user.id,
            len(updated_items),
            len(failed_items),
            [item["id"] for item in updated_items],
        )

        try:
            db.commit()
            logger.info(
                "[SUMMARY_TAG_BATCH] commit success user_id=%s updated_count=%s",
                user.id,
                len(updated_items),
            )
        except Exception as e:
            db.rollback()
            logger.exception(
                "[SUMMARY_TAG_BATCH] commit failed user_id=%s error=%s",
                user.id,
                str(e),
            )
            raise HTTPException(
                status_code=500,
                detail=f"요약 태그 저장 실패: {str(e)}",
            )

        verify_ids = [item["id"] for item in updated_items]
        verify_rows = []
        if verify_ids:
            verify_rows = (
                db.query(DiaryEntry)
                .filter(
                    DiaryEntry.user_id == user.id,
                    DiaryEntry.id.in_(verify_ids),
                )
                .order_by(DiaryEntry.entry_date.asc())
                .all()
            )

        logger.info(
            "[SUMMARY_TAG_BATCH] verify rows=%s",
            json.dumps(
                [
                    {
                        "id": row.id,
                        "entry_date": str(row.entry_date),
                        "summary_tag": row.summary_tag,
                    }
                    for row in verify_rows
                ],
                ensure_ascii=False,
            ),
        )

        finished_at = kst_now()
        elapsed_ms = int((finished_at - started_at).total_seconds() * 1000)

        result = {
            "message": f"{len(updated_items)}개의 일기 요약 태그를 생성했습니다.",
            "updated_count": len(updated_items),
            "items": updated_items,
            "failed_count": len(failed_items),
            "failed_items": failed_items,
            "month": month,
            "force": force,
            "limit": limit,
            "elapsed_ms": elapsed_ms,
        }

        logger.info(
            "[SUMMARY_TAG_BATCH] done result=%s",
            json.dumps(result, ensure_ascii=False),
        )

        return result

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