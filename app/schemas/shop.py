from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class ShopItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    item_type: str
    image_url: Optional[str] = None
    is_active: bool = True


class ShopItemCreate(ShopItemBase):
    pass


class ShopItemResponse(ShopItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserPurchaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    item_id: int
    purchase_date: datetime
    item: ShopItemResponse