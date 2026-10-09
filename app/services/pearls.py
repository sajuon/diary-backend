"""
진주 지급/사용 로직.

보상 규칙
- 출석      +2 : 하루 첫 앱 접속 (KST 날짜 기준 1번)
- 운세 보기 +2 : 오늘의 하루 / 사주 운세 중 하나를 처음 볼 때 (하루 1번)
- 일기 작성 +2 : 자유형·질문형·소급 작성 모두 포함, 작성한 날 기준 하루 1번
- 편지 피드백 +2 : 좋아요/아쉬워요 + 한마디를 보낼 때 (편지 1통당 1번)
- 오늘의 포춘쿠키 무료 → +1~30 랜덤 (하루 1개)
- 상점 포춘쿠키 -5 → +1~50 랜덤 (하루 1개)
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.fortune_cookie import FortuneCookie
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

COOKIE_FREE = "free"  # 오늘의 포춘쿠키 (무료, 하루 1개)
COOKIE_PAID = "paid"  # 상점 포춘쿠키 (5진주, 하루 1개)

# (진주 개수, 확률 %) — 합계 100
# 상점 쿠키: 기대값 약 4.2개
FORTUNE_COOKIE_TABLE: list[tuple[int, float]] = [
    (1, 35.0),
    (3, 30.0),
    (5, 20.0),
    (10, 12.0),
    (20, 2.5),
    (50, 0.5),
]

# 오늘의 무료 쿠키: 기대값 약 1.9개
FREE_COOKIE_TABLE: list[tuple[int, float]] = [
    (1, 55.0),
    (2, 33.0),
    (5, 11.5),
    (30, 0.5),
]

COOKIE_TABLES = {COOKIE_FREE: FREE_COOKIE_TABLE, COOKIE_PAID: FORTUNE_COOKIE_TABLE}
COOKIE_PRICES = {COOKIE_FREE: 0, COOKIE_PAID: FORTUNE_COOKIE_PRICE}

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

    # 보상 지급이 실패해도 일기 저장·운세 조회 같은 본 요청은 실패하면 안 된다.
    try:
        exists = (
            db.query(PearlTransaction.id)
            .filter(
                PearlTransaction.user_id == user_id,
                PearlTransaction.reason == reason,
                PearlTransaction.ref_key == ref_key,
            )
            .first()
        )
    except Exception:
        db.rollback()
        logger.exception("[PEARL] reward check failed user_id=%s reason=%s", user_id, reason)
        return None
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


def roll_fortune_cookie(kind: str = COOKIE_PAID) -> int:
    table = COOKIE_TABLES[kind]
    point = _rng.uniform(0, 100)
    acc = 0.0
    for amount, chance in table:
        acc += chance
        if point < acc:
            return amount
    return table[0][0]


class CookieError(Exception):
    """code: "already_opened" | "not_enough_pearls" """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def cookie_to_dict(row: FortuneCookie) -> dict:
    return {
        "kind": row.kind,
        "reward": row.reward,
        "is_jackpot": row.reward == COOKIE_TABLES[row.kind][-1][0],
        "message": row.message,
    }


def get_today_cookies(db: Session, user_id: int) -> dict[str, FortuneCookie]:
    rows = (
        db.query(FortuneCookie)
        .filter(FortuneCookie.user_id == user_id, FortuneCookie.date_key == kst_today_key())
        .all()
    )
    return {row.kind: row for row in rows}


def recent_cookie_messages(db: Session, user_id: int, limit: int = 10) -> list[str]:
    rows = (
        db.query(FortuneCookie.message)
        .filter(FortuneCookie.user_id == user_id)
        .order_by(FortuneCookie.id.desc())
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows]


def check_can_open_cookie(db: Session, user_id: int, kind: str) -> None:
    """문구를 만들기(LLM 호출) 전에 미리 확인. 못 열면 CookieError."""
    if kind in get_today_cookies(db, user_id):
        raise CookieError("already_opened")
    if _current_balance(db, user_id) < COOKIE_PRICES[kind]:
        raise CookieError("not_enough_pearls")


def open_fortune_cookie(
    db: Session, user_id: int, kind: str, message: str, source: str = "llm"
) -> dict:
    """
    포춘쿠키 1개 개봉. 종류별 하루 1개.
    상점 쿠키는 진주 차감과 지급을, 무료 쿠키는 지급을 한 트랜잭션으로 처리한다.
    """
    price = COOKIE_PRICES[kind]
    date_key = kst_today_key()

    try:
        if price > 0:
            deducted = (
                db.query(User)
                .filter(User.id == user_id, User.pearls >= price)
                .update({User.pearls: User.pearls - price}, synchronize_session=False)
            )
            if not deducted:
                db.rollback()
                raise CookieError("not_enough_pearls")
            db.add(
                PearlTransaction(
                    user_id=user_id,
                    amount=-price,
                    reason="fortune_cookie_cost",
                    ref_key=date_key,
                    balance_after=_current_balance(db, user_id),
                )
            )

        reward = roll_fortune_cookie(kind)
        db.query(User).filter(User.id == user_id).update(
            {User.pearls: User.pearls + reward}, synchronize_session=False
        )
        balance = _current_balance(db, user_id)
        db.add(
            PearlTransaction(
                user_id=user_id,
                amount=reward,
                reason="fortune_cookie_reward" if kind == COOKIE_PAID else "free_cookie_reward",
                ref_key=date_key,
                balance_after=balance,
            )
        )
        row = FortuneCookie(
            user_id=user_id,
            kind=kind,
            date_key=date_key,
            reward=reward,
            message=message,
            source=source,
        )
        db.add(row)
        db.commit()
    except CookieError:
        raise
    except IntegrityError:
        # 같은 날 같은 종류를 동시에 두 번 연 경우 → 전부 취소
        db.rollback()
        raise CookieError("already_opened")
    except Exception:
        db.rollback()
        logger.exception("[PEARL] fortune cookie failed user_id=%s kind=%s", user_id, kind)
        raise

    logger.info(
        "[PEARL] fortune cookie user_id=%s kind=%s reward=%s balance=%s source=%s",
        user_id, kind, reward, balance, source,
    )
    return {**cookie_to_dict(row), "price": price, "balance": balance}
