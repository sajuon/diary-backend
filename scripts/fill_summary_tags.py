import asyncio
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from app.core.database import SessionLocal

# 모델 registry 등록용 import
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.letter import OtterLetter
from app.models.profile import UserBirthProfile
from app.models.notification_settings import NotificationSettings
from app.models.auth_token import AuthToken
from app.models.diary_question import DiaryQuestion
from app.models.fortune import DailyFortune
from app.models.shop import ShopItem, UserPurchase
from app.models.web_push_subscription import WebPushSubscription

from app.services.diary_tag_service import generate_summary_tag


async def fill_summary_tags(force: bool = False):
    db = SessionLocal()
    updated_count = 0

    try:
        query = db.query(DiaryEntry).order_by(DiaryEntry.entry_date.asc())

        if not force:
            query = query.filter(
                (DiaryEntry.summary_tag.is_(None)) | (DiaryEntry.summary_tag == "")
            )

        entries = query.all()

        print(f"대상 일기 수: {len(entries)}")

        for entry in entries:
            try:
                tag = await generate_summary_tag(entry.content or "")
                entry.summary_tag = tag
                updated_count += 1
                print(
                    f"[{updated_count}] id={entry.id}, date={entry.entry_date}, tag={tag}"
                )
            except Exception as e:
                print(
                    f"[ERROR] id={entry.id}, date={entry.entry_date}, error={str(e)}"
                )

        db.commit()
        print(f"\n완료: {updated_count}개 summary_tag 업데이트")

    except Exception as e:
        db.rollback()
        print(f"\n전체 작업 실패: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(fill_summary_tags(force=True))