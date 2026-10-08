from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.room import DEFAULT_THEME_KEY, UserRoom
from app.models.shop import ShopItem, UserPurchase
from app.models.user import User
from app.schemas.room import RoomResponse, RoomThemeUpdateRequest

router = APIRouter(prefix="/api/room", tags=["Room"])


def _owned_theme_keys(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(ShopItem.item_key)
        .join(UserPurchase, UserPurchase.item_id == ShopItem.id)
        .filter(
            UserPurchase.user_id == user_id,
            ShopItem.item_type == "theme",
            ShopItem.item_key.isnot(None),
        )
        .all()
    )
    return [DEFAULT_THEME_KEY] + sorted({r[0] for r in rows})


def _get_or_create_room(db: Session, user_id: int) -> UserRoom:
    room = db.query(UserRoom).filter(UserRoom.user_id == user_id).first()
    if room is None:
        room = UserRoom(user_id=user_id, theme_key=DEFAULT_THEME_KEY)
        db.add(room)
        db.commit()
        db.refresh(room)
    return room


@router.get("", response_model=RoomResponse)
def get_room(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned = _owned_theme_keys(db, user.id)
    room = db.query(UserRoom).filter(UserRoom.user_id == user.id).first()
    theme_key = room.theme_key if room else DEFAULT_THEME_KEY
    if theme_key not in owned:
        theme_key = DEFAULT_THEME_KEY
    return {"theme_key": theme_key, "owned_theme_keys": owned}


@router.put("/theme", response_model=RoomResponse)
def set_room_theme(
    payload: RoomThemeUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned = _owned_theme_keys(db, user.id)
    if payload.theme_key not in owned:
        raise HTTPException(status_code=403, detail="아직 구매하지 않은 테마예요")

    room = _get_or_create_room(db, user.id)
    room.theme_key = payload.theme_key
    db.commit()
    return {"theme_key": room.theme_key, "owned_theme_keys": owned}
