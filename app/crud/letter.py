from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date

from app.models.letter import OtterLetter


def get_letter_by_entry_id(db: Session, diary_entry_id: int) -> Optional[OtterLetter]:
    return db.query(OtterLetter).filter(OtterLetter.diary_entry_id == diary_entry_id).first()


def get_letter_by_date(db: Session, user_id: int, letter_date: date) -> Optional[OtterLetter]:
    return (
        db.query(OtterLetter)
        .filter(OtterLetter.user_id == user_id, OtterLetter.letter_date == letter_date)
        .first()
    )


def create_letter(
    db: Session,
    user_id: int,
    diary_entry_id: int,
    letter_date: date,
    content: str,
    element_hint=None,
    model: Optional[str] = None,
) -> OtterLetter:
    letter = OtterLetter(
        user_id=user_id,
        diary_entry_id=diary_entry_id,
        letter_date=letter_date,
        content=content,
        element_hint=element_hint,
        model=model,
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    return letter


def get_or_create_letter(
    db: Session,
    user_id: int,
    diary_entry_id: int,
    letter_date: date,
    generated: dict,
) -> OtterLetter:
    """
    generated 예:
    { "content": "...", "element_hint": {...}, "model": "gpt-..." }
    """
    exists = get_letter_by_entry_id(db, diary_entry_id)
    if exists:
        return exists

    return create_letter(
        db=db,
        user_id=user_id,
        diary_entry_id=diary_entry_id,
        letter_date=letter_date,
        content=generated.get("content", ""),
        element_hint=generated.get("element_hint"),
        model=generated.get("model"),
    )


def list_letters_between(
    db: Session,
    user_id: int,
    from_date: date,
    to_date: date,
) -> List[OtterLetter]:
    return (
        db.query(OtterLetter)
        .filter(
            OtterLetter.user_id == user_id,
            OtterLetter.letter_date >= from_date,
            OtterLetter.letter_date <= to_date,
        )
        .order_by(OtterLetter.letter_date.desc())
        .all()
    )
