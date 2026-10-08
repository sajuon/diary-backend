from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.room import DEFAULT_THEME_KEY, UserRoom
from app.models.shop import ShopItem, UserPurchase
from app.models.user import User
from app.schemas.room import (
    LetterPaperUpdateRequest,
    PlacementsUpdateRequest,
    RoomResponse,
    RoomThemeUpdateRequest,
)

router = APIRouter(prefix="/api/room", tags=["Room"])

ITEM_TYPE_THEME = "theme"
ITEM_TYPE_LETTER_PAPER = "letter_paper"
ITEM_TYPE_ROOM_ITEM = "room_item"


def _purchased_keys(db: Session, user_id: int, item_type: str) -> list[str]:
    """구매한 상품 키 목록."""
    rows = (
        db.query(ShopItem.item_key)
        .join(UserPurchase, UserPurchase.item_id == ShopItem.id)
        .filter(
            UserPurchase.user_id == user_id,
            ShopItem.item_type == item_type,
            ShopItem.item_key.isnot(None),
        )
        .all()
    )
    return sorted({r[0] for r in rows})


def _owned_keys(db: Session, user_id: int, item_type: str) -> list[str]:
    """테마·편지지 보유 목록. "default"(무료 기본)는 항상 포함."""
    return [DEFAULT_THEME_KEY] + _purchased_keys(db, user_id, item_type)


def _get_or_create_room(db: Session, user_id: int) -> UserRoom:
    room = db.query(UserRoom).filter(UserRoom.user_id == user_id).first()
    if room is None:
        room = UserRoom(
            user_id=user_id,
            theme_key=DEFAULT_THEME_KEY,
            letter_paper_key=DEFAULT_THEME_KEY,
        )
        db.add(room)
        db.commit()
        db.refresh(room)
    return room


def _room_payload(db: Session, user_id: int) -> dict:
    owned_themes = _owned_keys(db, user_id, ITEM_TYPE_THEME)
    owned_papers = _owned_keys(db, user_id, ITEM_TYPE_LETTER_PAPER)
    room = db.query(UserRoom).filter(UserRoom.user_id == user_id).first()

    theme_key = room.theme_key if room else DEFAULT_THEME_KEY
    paper_key = (room.letter_paper_key if room else None) or DEFAULT_THEME_KEY

    # 상품이 비활성화되는 등 소유 목록에 없으면 기본값으로 보여준다
    if theme_key not in owned_themes:
        theme_key = DEFAULT_THEME_KEY
    if paper_key not in owned_papers:
        paper_key = DEFAULT_THEME_KEY

    owned_items = _purchased_keys(db, user_id, ITEM_TYPE_ROOM_ITEM)
    owned_item_set = set(owned_items)
    placements = [
        p for p in ((room.placements if room else None) or [])
        if isinstance(p, dict) and p.get("item_key") in owned_item_set
    ]

    return {
        "theme_key": theme_key,
        "owned_theme_keys": owned_themes,
        "letter_paper_key": paper_key,
        "owned_letter_paper_keys": owned_papers,
        "owned_room_item_keys": owned_items,
        "placements": placements,
    }


@router.get("", response_model=RoomResponse)
def get_room(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _room_payload(db, user.id)


@router.put("/theme", response_model=RoomResponse)
def set_room_theme(
    payload: RoomThemeUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.theme_key not in _owned_keys(db, user.id, ITEM_TYPE_THEME):
        raise HTTPException(status_code=403, detail="아직 구매하지 않은 테마예요")

    room = _get_or_create_room(db, user.id)
    room.theme_key = payload.theme_key
    db.commit()
    return _room_payload(db, user.id)


@router.put("/letter-paper", response_model=RoomResponse)
def set_letter_paper(
    payload: LetterPaperUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.letter_paper_key not in _owned_keys(db, user.id, ITEM_TYPE_LETTER_PAPER):
        raise HTTPException(status_code=403, detail="아직 구매하지 않은 편지지예요")

    room = _get_or_create_room(db, user.id)
    room.letter_paper_key = payload.letter_paper_key
    db.commit()
    return _room_payload(db, user.id)


@router.put("/placements", response_model=RoomResponse)
def set_placements(
    payload: PlacementsUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """소품 배치 전체를 저장한다. 산 소품만, 소품당 1번만 놓을 수 있다."""
    owned = set(_purchased_keys(db, user.id, ITEM_TYPE_ROOM_ITEM))
    seen: set[str] = set()
    cleaned = []
    for p in payload.placements:
        if p.item_key not in owned:
            raise HTTPException(status_code=403, detail="아직 구매하지 않은 소품이에요")
        if p.item_key in seen:
            raise HTTPException(status_code=400, detail="같은 소품은 한 번만 놓을 수 있어요")
        seen.add(p.item_key)
        cleaned.append({"item_key": p.item_key, "x": round(p.x, 2), "y": round(p.y, 2)})

    room = _get_or_create_room(db, user.id)
    room.placements = cleaned
    db.commit()
    return _room_payload(db, user.id)
