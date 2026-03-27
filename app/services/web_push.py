import json
import os

from dotenv import load_dotenv
from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session

from app.models.notification_settings import NotificationSettings
from app.models.web_push_subscription import WebPushSubscription

load_dotenv()

VAPID_PRIVATE_KEY = os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT = os.getenv("WEB_PUSH_VAPID_SUBJECT", "mailto:admin@example.com")


def get_vapid_public_key() -> str:
    return VAPID_PUBLIC_KEY


def get_or_create_notification_settings(
    db: Session,
    user_id: int,
) -> NotificationSettings:
    settings = (
        db.query(NotificationSettings)
        .filter(NotificationSettings.user_id == user_id)
        .first()
    )
    if settings:
        return settings

    settings = NotificationSettings(
        user_id=user_id,
        push_enabled=True,
        fortune_enabled=True,
        diary_reminder_enabled=True,
        reply_enabled=True,
        timezone="Asia/Seoul",
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def send_web_push_to_subscription(
    subscription: WebPushSubscription,
    title: str,
    body: str,
    url: str = "/",
) -> bool:
    if not subscription.is_active:
        return False

    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        raise RuntimeError("VAPID 키가 설정되지 않았습니다.")

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "url": url,
        }
    )

    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
        },
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True
    except WebPushException as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)

        if status_code in (404, 410):
            subscription.is_active = False

        return False


def send_web_push_to_user(
    db: Session,
    user_id: int,
    title: str,
    body: str,
    url: str = "/",
    notification_type: str | None = None,
) -> dict:
    settings = get_or_create_notification_settings(db, user_id)

    if not settings.push_enabled:
        return {"sent": 0, "skipped": 0, "reason": "push_disabled"}

    if notification_type == "fortune" and not settings.fortune_enabled:
        return {"sent": 0, "skipped": 0, "reason": "fortune_disabled"}

    if notification_type == "diary_reminder" and not settings.diary_reminder_enabled:
        return {"sent": 0, "skipped": 0, "reason": "diary_reminder_disabled"}

    if notification_type == "reply" and not settings.reply_enabled:
        return {"sent": 0, "skipped": 0, "reason": "reply_disabled"}

    subscriptions = (
        db.query(WebPushSubscription)
        .filter(
            WebPushSubscription.user_id == user_id,
            WebPushSubscription.is_active == True,
        )
        .all()
    )

    if not subscriptions:
        return {"sent": 0, "skipped": 0, "reason": "no_active_subscriptions"}

    sent = 0
    skipped = 0

    for subscription in subscriptions:
        ok = send_web_push_to_subscription(
            subscription=subscription,
            title=title,
            body=body,
            url=url,
        )
        if ok:
            sent += 1
        else:
            skipped += 1

    db.commit()
    return {"sent": sent, "skipped": skipped, "reason": None}
