from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.shop import ShopItem, UserPurchase
from app.schemas.shop import ShopItemResponse, UserPurchaseResponse


router = APIRouter(prefix="/api/shop", tags=["Shop"])


@router.get("/items", response_model=list[ShopItemResponse])
def list_shop_items(
    item_type: str = None,
    db: Session = Depends(get_db),
):
    query = db.query(ShopItem).filter(ShopItem.is_active == True)

    if item_type:
        query = query.filter(ShopItem.item_type == item_type)

    items = query.order_by(ShopItem.id.asc()).all()
    return items


@router.post("/purchase/{item_id}", response_model=UserPurchaseResponse)
def purchase_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # 1. 구매 대상 아이템 확인
        item = (
            db.query(ShopItem)
            .filter(
                ShopItem.id == item_id,
                ShopItem.is_active == True,
            )
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")

        # 2. 최신 사용자 정보 조회
        db_user = (
            db.query(User)
            .filter(User.id == user.id)
            .first()
        )
        if not db_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

        # 3. 이미 구매한 아이템인지 확인
        existing_purchase = (
            db.query(UserPurchase)
            .filter(
                UserPurchase.user_id == db_user.id,
                UserPurchase.item_id == item.id,
            )
            .first()
        )
        if existing_purchase:
            raise HTTPException(status_code=400, detail="이미 구매한 아이템입니다")

        # 4. 진주 수 확인
        price = int(item.price)
        current_pearls = int(db_user.pearls or 0)

        if current_pearls < price:
            raise HTTPException(status_code=400, detail="진주가 부족합니다")

        next_pearls = current_pearls - price
        if next_pearls < 0:
            raise HTTPException(status_code=400, detail="진주가 부족합니다")

        # 5. 진주 차감
        db_user.pearls = next_pearls

        # 6. 구매 내역 생성
        purchase = UserPurchase(
            user_id=db_user.id,
            item_id=item.id,
        )
        db.add(purchase)

        # 7. DB 반영
        db.flush()
        db.commit()

        # 8. 관계 포함해서 다시 조회
        created_purchase = (
            db.query(UserPurchase)
            .options(joinedload(UserPurchase.item))
            .filter(UserPurchase.id == purchase.id)
            .first()
        )
        if not created_purchase:
            raise HTTPException(status_code=500, detail="구매 정보 조회에 실패했습니다")

        return created_purchase

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="이미 구매한 아이템입니다")

    except Exception as e:
        db.rollback()
        print(f"[SHOP PURCHASE ERROR] {e}")
        raise HTTPException(status_code=500, detail="구매 처리 중 오류가 발생했습니다")


@router.get("/purchases", response_model=list[UserPurchaseResponse])
def list_user_purchases(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    purchases = (
        db.query(UserPurchase)
        .options(joinedload(UserPurchase.item))
        .filter(UserPurchase.user_id == user.id)
        .order_by(UserPurchase.purchase_date.desc(), UserPurchase.id.desc())
        .all()
    )
    return purchases