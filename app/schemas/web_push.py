from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WebPushKeys(BaseModel):
    p256dh: str
    auth: str


class WebPushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: WebPushKeys


class WebPushSubscribeRequest(BaseModel):
    subscription: WebPushSubscriptionCreate
    user_agent: Optional[str] = None


class WebPushUnsubscribeRequest(BaseModel):
    endpoint: str


class WebPushTestRequest(BaseModel):
    title: str = "해도리 테스트 알림"
    body: str = "웹 푸시가 정상적으로 도착했어."
    url: str = "/notification-settings"


class WebPushSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    endpoint: str
    p256dh: str
    auth: str
    user_agent: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WebPushPublicKeyResponse(BaseModel):
    public_key: str