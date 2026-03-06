from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.web_push_subscription import WebPushSubscription
from app.schemas.web_push import (
    WebPushPublicKeyResponse,
    WebPushSubscribeRequest,
    WebPushSubscriptionResponse,
    WebPushTestRequest,
    WebPushUnsubscribeRequest,
)
from app.services.web_push import get_vapid_public_key, send_web_push_to_user

router = APIRouter(prefix="/api/web-push", tags=["Web Push"])


@router.get("/public-key", response_model=WebPushPublicKeyResponse)
def get_public_key():
    public_key = get_vapid_public_key()
    if not public_key:
        raise HTTPException(status_code=500, detail="VAPID 공개키가 없습니다.")
    return {"public_key": public_key}


@router.post("/subscribe", response_model=WebPushSubscriptionResponse)
def subscribe_web_push(
    data: WebPushSubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(WebPushSubscription)
        .filter(WebPushSubscription.endpoint == data.subscription.endpoint)
        .first()
    )

    if existing:
        existing.user_id = user.id
        existing.p256dh = data.subscription.keys.p256dh
        existing.auth = data.subscription.keys.auth
        existing.user_agent = data.user_agent
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    row = WebPushSubscription(
        user_id=user.id,
        endpoint=data.subscription.endpoint,
        p256dh=data.subscription.keys.p256dh,
        auth=data.subscription.keys.auth,
        user_agent=data.user_agent,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/unsubscribe")
def unsubscribe_web_push(
    data: WebPushUnsubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(WebPushSubscription)
        .filter(
            WebPushSubscription.user_id == user.id,
            WebPushSubscription.endpoint == data.endpoint,
        )
        .first()
    )

    if row:
        row.is_active = False
        db.commit()

    return {"ok": True}


@router.post("/test")
def send_test_web_push(
    data: WebPushTestRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = send_web_push_to_user(
        db=db,
        user_id=user.id,
        title=data.title,
        body=data.body,
        url=data.url,
        notification_type=None,
    )
    return {"ok": True, **result}