"""
누락된 자동 답장 편지를 지정한 일기 ID에 대해 생성한다.

letter_jobs.py가 created_at(UTC)을 KST로 잘못 읽던 버그로
KST 00:00~09:00에 쓴 당일 일기가 자동 답장에서 빠진 경우 복구용.

사용법 (diary-backend 폴더에서):
    venv/bin/python scripts/backfill_letters.py 121 124 127          # 미리보기만
    venv/bin/python scripts/backfill_letters.py 121 124 127 --apply  # 실제 생성

- 이미 편지가 있는 일기, free가 아닌 일기, 당일 작성이 아닌 일기는 건너뛴다.
- 푸시 알림은 보내지 않는다. 편지는 읽지 않음 상태로 편지함에 들어간다.
"""

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
from app.models.profile import UserBirthProfile  # noqa: F401
from app.models.notification_settings import NotificationSettings  # noqa: F401
from app.models.auth_token import AuthToken  # noqa: F401
from app.models.diary_question import DiaryQuestion  # noqa: F401
from app.models.fortune import DailyFortune
from app.models.shop import ShopItem, UserPurchase  # noqa: F401
from app.models.web_push_subscription import WebPushSubscription  # noqa: F401

from app.services.letter_generator import generate_otter_letter
from app.services.streak import is_on_time


async def backfill(entry_ids: list[int], apply: bool) -> None:
    db = SessionLocal()
    created = 0
    try:
        for entry_id in entry_ids:
            entry = db.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
            if entry is None:
                print(f"[skip] entry {entry_id}: 없음")
                continue
            if entry.diary_type != "free":
                print(f"[skip] entry {entry_id}: diary_type={entry.diary_type}")
                continue
            if entry.created_at is None or not is_on_time(entry.entry_date, entry.created_at):
                print(f"[skip] entry {entry_id}: 당일 작성 아님")
                continue
            if db.query(OtterLetter).filter(OtterLetter.diary_entry_id == entry.id).first():
                print(f"[skip] entry {entry_id}: 이미 편지 있음")
                continue

            user = db.query(User).filter(User.id == entry.user_id).first()
            if user is None:
                print(f"[skip] entry {entry_id}: user {entry.user_id} 없음")
                continue

            if not apply:
                print(f"[dry-run] entry {entry_id}: user {user.id}, {entry.entry_date} → 생성 대상")
                continue

            fortune = (
                db.query(DailyFortune)
                .filter(
                    DailyFortune.user_id == user.id,
                    DailyFortune.fortune_date == entry.entry_date,
                )
                .first()
            )

            try:
                data = await generate_otter_letter(user=user, diary_entry=entry, fortune=fortune)
                letter = OtterLetter(
                    user_id=user.id,
                    diary_entry_id=entry.id,
                    letter_date=entry.entry_date,
                    content=data.get("content", ""),
                    element_hint=data.get("element_hint"),
                    model=data.get("model"),
                    is_read=False,
                    read_at=None,
                )
                db.add(letter)
                db.commit()
                db.refresh(letter)
                created += 1
                print(f"[created] entry {entry_id}: letter {letter.id} (model={letter.model})")
            except Exception as e:  # noqa: BLE001
                db.rollback()
                print(f"[fail] entry {entry_id}: {e}")

        if not apply:
            print("\n미리보기만 했어요. 실제로 만들려면 --apply를 붙여서 다시 실행하세요.")
        else:
            print(f"\n완료: {created}개 생성")
    finally:
        db.close()


def main() -> None:
    args = sys.argv[1:]
    apply = "--apply" in args
    ids = [int(a) for a in args if a.isdigit()]
    if not ids:
        print(__doc__)
        sys.exit(1)
    asyncio.run(backfill(ids, apply))


if __name__ == "__main__":
    main()
