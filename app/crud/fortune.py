from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date

from app.models.fortune import DailyFortune


def get_fortune_by_date(db: Session, user_id: int, fortune_date: date) -> Optional[DailyFortune]:
    return (
        db.query(DailyFortune)
        .filter(DailyFortune.user_id == user_id, DailyFortune.fortune_date == fortune_date)
        .first()
    )


def create_fortune(
    db: Session,
    user_id: int,
    fortune_date: date,
    love: str,
    study: str,
    caution: str,
    good_thing: str,
    ritual: str,
    element_hint=None,
    model: Optional[str] = None,
) -> DailyFortune:
    fortune = DailyFortune(
        user_id=user_id,
        fortune_date=fortune_date,
        love=love,
        study=study,
        caution=caution,
        good_thing=good_thing,
        ritual=ritual,
        element_hint=element_hint,
        model=model,
    )
    db.add(fortune)
    db.commit()
    db.refresh(fortune)
    return fortune


def get_or_create_fortune(
    db: Session,
    user_id: int,
    fortune_date: date,
    generated: dict,
) -> DailyFortune:
    """
    generated 예:
    {
      "love": "...", "study": "...", "caution": "...",
      "good_thing": "...", "ritual": "...",
      "element_hint": {...}, "model": "gpt-..."
    }
    """
    fortune = get_fortune_by_date(db, user_id, fortune_date)
    if fortune:
        return fortune

    return create_fortune(
        db=db,
        user_id=user_id,
        fortune_date=fortune_date,
        love=generated.get("love", ""),
        study=generated.get("study", ""),
        caution=generated.get("caution", ""),
        good_thing=generated.get("good_thing", ""),
        ritual=generated.get("ritual", ""),
        element_hint=generated.get("element_hint"),
        model=generated.get("model"),
    )


def list_fortunes_between(
    db: Session,
    user_id: int,
    from_date: date,
    to_date: date,
) -> List[DailyFortune]:
    return (
        db.query(DailyFortune)
        .filter(
            DailyFortune.user_id == user_id,
            DailyFortune.fortune_date >= from_date,
            DailyFortune.fortune_date <= to_date,
        )
        .order_by(DailyFortune.fortune_date.desc())
        .all()
    )
