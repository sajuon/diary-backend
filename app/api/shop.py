from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.shop import ShopItem, UserPurchase
from app.schemas.shop import ShopItemResponse, UserPurchaseResponse


router = APIRouter(prefix="/api/shop", tags=["Shop"])


@router.get("/items", response_model=List[ShopItemResponse])
def list_shop_items(
    item_type: str = None,
    db: Session = Depends(get_db),
):
    query = db.query(ShopItem).filter(ShopItem.is_active == True)
    if item_type:
        query = query.filter(ShopItem.item_type == item_type)
    
    items = query.all()
    return items


@router.post("/purchase/{item_id}", response_model=UserPurchaseResponse)
def purchase_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(ShopItem).filter(ShopItem.id == item_id, ShopItem.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")

    # 이미 구매했는지 확인 (중복 구매 방지)
    existing = db.query(UserPurchase).filter(
        UserPurchase.user_id == user.id,
        UserPurchase.item_id == item_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 구매한 아이템입니다")

    # 진주 잔액 확인
    if user.pearls < item.price:
        raise HTTPException(status_code=400, detail="진주가 부족합니다")

    # 진주 차감
    user.pearls -= int(item.price)

    purchase = UserPurchase(
        user_id=user.id,
        item_id=item_id
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    
    return purchase


@router.get("/purchases", response_model=List[UserPurchaseResponse])
def list_user_purchases(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    purchases = (
        db.query(UserPurchase)
        .filter(UserPurchase.user_id == user.id)
        .order_by(UserPurchase.purchase_date.desc())
        .all()
    )
    return purchases