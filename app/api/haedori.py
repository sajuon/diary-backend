from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.personality import (
    SnackError,
    buy_snack,
    feed_snack,
    get_state,
    state_payload,
)

router = APIRouter(prefix="/api/haedori", tags=["Haedori"])


class BuySnackRequest(BaseModel):
    quantity: int = Field(default=1, ge=1, le=10)


@router.get("")
def get_haedori(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """해도리 성격 + 간식 목록(가격, 효과, 보유 개수)."""
    return state_payload(get_state(db, user.id))


@router.post("/snacks/{snack_key}/buy")
def buy(
    snack_key: str,
    payload: BuySnackRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return buy_snack(db, user.id, snack_key, (payload.quantity if payload else 1))
    except SnackError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/snacks/{snack_key}/feed")
def feed(
    snack_key: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return feed_snack(db, user.id, snack_key)
    except SnackError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
