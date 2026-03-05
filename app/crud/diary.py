from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date

from app.models.diary import DiaryEntry


def get_diary_by_date(db: Session, user_id: int, entry_date: date) -> Optional[DiaryEntry]:
    return (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user_id, DiaryEntry.entry_date == entry_date)
        .first()
    )


def create_diary_entry(
    db: Session,
    user_id: int,
    entry_date: date,
    content: str,
    mood_tags=None,
) -> DiaryEntry:
    entry = DiaryEntry(
        user_id=user_id,
        entry_date=entry_date,
        content=content,
        mood_tags=mood_tags,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_diaries_between(
    db: Session,
    user_id: int,
    from_date: date,
    to_date: date,
) -> List[DiaryEntry]:
    return (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == user_id,
            DiaryEntry.entry_date >= from_date,
            DiaryEntry.entry_date <= to_date,
        )
        .order_by(DiaryEntry.entry_date.desc())
        .all()
    )
