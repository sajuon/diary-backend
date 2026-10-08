"""
진주 지급/사용 로직.

보상 규칙
- 출석      +2 : 하루 첫 앱 접속 (KST 날짜 기준 1번)
- 운세 보기 +2 : 오늘의 하루 / 사주 운세 중 하나를 처음 볼 때 (하루 1번)
- 일기 작성 +2 : 자유형·질문형·소급 작성 모두 포함, 작성한 날 기준 하루 1번
- 편지 피드백 +2 : 좋아요/아쉬워요 + 한마디를 보낼 때 (편지 1통당 1번)
- 포춘쿠키  -5 → +1~50 랜덤
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.pearl import PearlTransaction
from app.models.user import User

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

REWARD_ATTENDANCE = "attendance"
REWARD_FORTUNE = "fortune"
REWARD_DIARY = "diary"
REWARD_LETTER_FEEDBACK = "letter_feedback"

REWARD_AMOUNTS = {
    REWARD_ATTENDANCE: 2,
    REWARD_FORTUNE: 2,
    REWARD_DIARY: 2,
    REWARD_LETTER_FEEDBACK: 2,
}

REWARD_LABELS = {
    REWARD_ATTENDANCE: "출석",
    REWARD_FORTUNE: "운세 보기",
    REWARD_DIARY: "일기 작성",
    REWARD_LETTER_FEEDBACK: "피드백",
}

FORTUNE_COOKIE_PRICE = 5

# (진주 개수, 확률 %) — 합계 100, 기대값 약 4.2개
FORTUNE_COOKIE_TABLE: list[tuple[int, float]] = [
    (1, 35.0),
    (3, 30.0),
    (5, 20.0),
    (10, 12.0),
    (20, 2.5),
    (50, 0.5),
]

_rng = secrets.SystemRandom()


def kst_today_key() -> str:
    return datetime.now(KST).date().isoformat()


def _current_balance(db: Session, user_id: int) -> int:
    value = db.query(User.pearls).filter(User.id == user_id).scalar()
    return int(value or 0)


def award_reward(db: Session, user_id: int, reason: str, ref_key: str) -> Optional[dict]:
    """
    보상을 1번만 지급한다. 이미 받은 보상이면 None.

    주의: 이 함수는 실패 시 db.rollback()을 호출하므로,
    호출하는 쪽의 다른 변경 사항은 먼저 commit한 뒤에 부른다.
    """
    amount = REWARD_AMOUNTS[reason]

    exists = (
        db.query(PearlTransaction.id)
        .filter(
            PearlTransaction.user_id == user_id,
            PearlTransaction.reason == reason,
            PearlTransaction.ref_key == ref_key,
        )
        .first()
    )
    if exists:
        return None

    try:
        db.query(User).filter(User.id == user_id).update(
            {User.pearls: User.pearls + amount}, synchronize_session=False
        )
        balance = _current_balance(db, user_id)
        db.add(
            PearlTransaction(
                user_id=user_id,
                amount=amount,
                reason=reason,
                ref_key=ref_key,
                balance_after=balance,
            )
        )
        db.commit()
    except IntegrityError:
        # 동시에 두 요청이 들어와 유니크 제약에 걸린 경우 → 지급 취소
        db.rollback()
        return None
    except Exception:
        db.rollback()
        logger.exception("[PEARL] award failed user_id=%s reason=%s", user_id, reason)
        return None

    logger.info("[PEARL] +%s %s user_id=%s balance=%s", amount, reason, user_id, balance)
    return {
        "amount": amount,
        "reason": reason,
        "label": REWARD_LABELS[reason],
        "balance": balance,
    }


def award_daily(db: Session, user_id: int, reason: str) -> Optional[dict]:
    return award_reward(db, user_id, reason, kst_today_key())


def roll_fortune_cookie() -> int:
    point = _rng.uniform(0, 100)
    acc = 0.0
    for amount, chance in FORTUNE_COOKIE_TABLE:
        acc += chance
        if point < acc:
            return amount
    return FORTUNE_COOKIE_TABLE[0][0]


def open_fortune_cookie(db: Session, user_id: int) -> Optional[dict]:
    """
    포춘쿠키 1개 구매 + 개봉. 진주가 부족하면 None.
    차감과 지급을 한 트랜잭션으로 처리한다.
    """
    deducted = (
        db.query(User)
        .filter(User.id == user_id, User.pearls >= FORTUNE_COOKIE_PRICE)
        .update({User.pearls: User.pearls - FORTUNE_COOKIE_PRICE}, synchronize_session=False)
    )
    if not deducted:
        db.rollback()
        return None

    reward = roll_fortune_cookie()

    try:
        after_cost = _current_balance(db, user_id)
        db.add(
            PearlTransaction(
                user_id=user_id,
                amount=-FORTUNE_COOKIE_PRICE,
                reason="fortune_cookie_cost",
                ref_key=None,
                balance_after=after_cost,
            )
        )
        db.query(User).filter(User.id == user_id).update(
            {User.pearls: User.pearls + reward}, synchronize_session=False
        )
        balance = _current_balance(db, user_id)
        db.add(
            PearlTransaction(
                user_id=user_id,
                amount=reward,
                reason="fortune_cookie_reward",
                ref_key=None,
                balance_after=balance,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("[PEARL] fortune cookie failed user_id=%s", user_id)
        raise

    logger.info("[PEARL] fortune cookie user_id=%s reward=%s balance=%s", user_id, reward, balance)
    return {
        "price": FORTUNE_COOKIE_PRICE,
        "reward": reward,
        "is_jackpot": reward == FORTUNE_COOKIE_TABLE[-1][0],
        "balance": balance,
    }
