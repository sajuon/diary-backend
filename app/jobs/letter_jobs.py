from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.session import SessionLocal  # 너희 프로젝트에 맞게 import 경로 조정 필요할 수 있음
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune
from app.models.letter import OtterLetter
from app.services.letter_generator import generate_otter_letter


def kst_today_date():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


async def generate_letters_for_today():
    """
    매일 23:00에 실행:
    - 오늘 일기 쓴 유저들 중
    - 아직 오늘 편지가 없는 경우
    - 편지 생성해서 저장
    """
    today = kst_today_date()

    db: Session = SessionLocal()
    try:
        # 오늘 일기 전체
        diaries = (
            db.query(DiaryEntry)
            .filter(DiaryEntry.entry_date == today)
            .all()
        )

        for entry in diaries:
            # 이미 오늘 편지 있으면 skip
            exists = (
                db.query(OtterLetter)
                .filter(OtterLetter.diary_entry_id == entry.id)
                .first()
            )
            if exists:
                continue

            user = db.query(User).filter(User.id == entry.user_id).first()
            if not user:
                continue

            fortune = (
                db.query(DailyFortune)
                .filter(DailyFortune.user_id == user.id, DailyFortune.fortune_date == today)
                .first()
            )

            data = await generate_otter_letter(user=user, diary_entry=entry, fortune=fortune)

            letter = OtterLetter(
                user_id=user.id,
                diary_entry_id=entry.id,
                letter_date=today,
                content=data.get("content", ""),
                element_hint=data.get("element_hint"),
                model=data.get("model"),
            )
            db.add(letter)

        db.commit()

    finally:
        db.close()