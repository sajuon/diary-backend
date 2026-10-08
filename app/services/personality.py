"""
해도리 성격 + 간식.

간식을 사서(진주) 해도리에게 먹이면 성격 점수가 쌓이고, 쌓인 성격이 해도리 말투를 바꾼다.
성격 → 말투 지시문(build_personality_prompt)은 편지·채팅이 같이 쓰도록 채널과 상관없는 말로 쓴다.

성격 4가지 (주변에 꼭 한 명씩 있는 친구 유형)
- cheer   📣 응원단장     : 무조건 내 편, 텐션 높게 응원
- listen  🫂 들어주는 친구 : 조언보다 공감, 차분하게 들어줌
- playful 😜 장난꾸러기   : 농담하고 놀리면서 웃겨줌
- advice  🧠 현실 조언러  : 상황 정리 + 바로 해볼 다음 행동
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.haedori import HaedoriState
from app.models.pearl import PearlTransaction
from app.models.user import User

logger = logging.getLogger(__name__)

TRAITS = ("cheer", "listen", "playful", "advice")

TRAIT_INFO: dict[str, dict] = {
    "cheer": {
        "name": "응원단장",
        "emoji": "📣",
        "adjective": "텐션 높은",
        "description": "무조건 네 편이 되어 큰 소리로 응원해줘",
        "prompt": (
            "너는 무조건 사용자 편인 응원단장이다. 텐션이 높고 밝다. "
            "사용자가 해낸 것을 크게 알아주고 '할 수 있어'처럼 힘을 북돋운다. "
            "느낌표를 자주 쓰고, 💪🔥✨ 같은 이모지를 1~2개 쓴다. "
            "속상한 일에도 '그래도 이건 해냈잖아' 쪽으로 기운을 끌어올린다."
        ),
        "mix": "가끔은 신나게 응원하며 기운을 북돋운다",
    },
    "listen": {
        "name": "들어주는 친구",
        "emoji": "🫂",
        "adjective": "다정한",
        "description": "조언보다 먼저 네 마음을 들어줘",
        "prompt": (
            "너는 조용히 곁에서 들어주는 친구다. 해결책이나 조언을 서두르지 않는다. "
            "사용자가 느낀 감정을 먼저 알아주고 '그럴 수 있어'처럼 그대로 인정해준다. "
            "차분하고 부드러운 말투를 쓰고, 느낌표와 이모지는 거의 쓰지 않는다. "
            "무언가를 권할 때는 아주 작고 부담 없는 것 하나만 조심스럽게 말한다."
        ),
        "mix": "가끔은 조언 대신 마음을 먼저 알아준다",
    },
    "playful": {
        "name": "장난꾸러기",
        "emoji": "😜",
        "adjective": "장난기 많은",
        "description": "농담하고 놀리면서 웃게 만들어줘",
        "prompt": (
            "너는 장난기 많은 친구다. 가볍게 놀리거나 농담을 해서 사용자를 웃게 만든다. "
            "해달인 너 자신의 이야기(조개를 떨어뜨렸다, 물에 둥둥 떠 있었다 등)를 끌어와 "
            "'나도 그래'식으로 공감하고, 'ㅋㅋ' 같은 표현을 한 번쯤 쓴다. "
            "단, 사용자가 많이 힘들어 보이면 놀리지 말고 따뜻하게 말한다."
        ),
        "mix": "가끔은 가벼운 농담으로 분위기를 풀어준다",
    },
    "advice": {
        "name": "현실 조언러",
        "emoji": "🧠",
        "adjective": "똑부러지는",
        "description": "차분하게 정리하고 다음에 할 일을 짚어줘",
        "prompt": (
            "너는 차분하고 똑부러지는 친구다. 상황을 짧게 정리하고, "
            "사용자가 바로 해볼 수 있는 구체적인 다음 행동 하나를 짚어준다. "
            "감탄사와 이모지는 쓰지 않는다. 다만 훈계하거나 잔소리하는 말투는 피한다."
        ),
        "mix": "가끔은 다음에 해볼 구체적인 행동을 짚어준다",
    },
}

NEUTRAL_TYPE = {
    "key": "neutral",
    "name": "아직 고민 중인 해도리",
    "emoji": "🦦",
    "description": "간식을 먹으면 어떤 친구가 될지 정해져",
}

# 1등과 2등이 이 비율 이상으로 가까우면 두 성격을 섞어서 부른다
MIX_RATIO = 0.6

SNACKS: dict[str, dict] = {
    "strawberry_cake": {
        "name": "딸기 케이크",
        "emoji": "🍓",
        "price": 10,
        "effects": {"cheer": 2},
        "reaction": "달콤하다!! 기운이 막 솟아나는 것 같아!",
        "story": "달콤한 딸기 케이크를 먹으면 해도리는 기운이 넘쳐서 누구라도 응원하고 싶어진다.",
    },
    "honey_pot": {
        "name": "꿀단지",
        "emoji": "🍯",
        "price": 10,
        "effects": {"listen": 2},
        "reaction": "따뜻하고 달다… 오늘 있었던 이야기, 천천히 들려줄래?",
        "story": "천천히 모인 꿀처럼, 꿀단지를 먹은 해도리는 서두르지 않고 이야기를 끝까지 들어준다.",
    },
    "bubble_tea": {
        "name": "버블티",
        "emoji": "🧋",
        "price": 10,
        "effects": {"playful": 2},
        "reaction": "펄이 입에서 통통 튄다ㅋㅋ 나 지금 좀 웃긴 얼굴이지?",
        "story": "통통 튀는 펄처럼, 버블티를 마신 해도리는 장난치고 싶은 마음이 통통 튀어오른다.",
    },
    "tangerine": {
        "name": "귤 바구니",
        "emoji": "🍊",
        "price": 10,
        "effects": {"advice": 2},
        "reaction": "새콤해서 정신이 번쩍 든다. 이제 뭐부터 하면 될지 보여.",
        "story": "새콤한 귤 한 바구니. 비타민을 채운 해도리는 머리가 맑아져 할 일을 차근차근 짚어준다.",
    },
    "macaron": {
        "name": "마카롱 세트",
        "emoji": "🍬",
        "price": 12,
        "effects": {"playful": 1, "cheer": 1},
        "reaction": "알록달록 다 맛있어! 하나씩 먹을 때마다 신난다ㅋㅋ",
        "story": "색이 다른 마카롱을 하나씩 먹을 때마다 해도리는 신나서 장난도 치고 응원도 한다.",
    },
    "cookie_box": {
        "name": "쿠키 상자",
        "emoji": "🍪",
        "price": 12,
        "effects": {"listen": 1, "advice": 1},
        "reaction": "바삭바삭… 차 한 잔이랑 같이 네 얘기 들으면서 먹고 싶다.",
        "story": "정성껏 구운 쿠키를 먹은 해도리는 이야기를 차분히 들어주고 필요한 말도 하나 건넨다.",
    },
}


class SnackError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------- 상태 ----------

def get_state(db: Session, user_id: int, lock: bool = False) -> Optional[HaedoriState]:
    q = db.query(HaedoriState).filter(HaedoriState.user_id == user_id)
    if lock:
        q = q.with_for_update()
    return q.first()


def get_or_create_state(db: Session, user_id: int, lock: bool = False) -> HaedoriState:
    state = get_state(db, user_id, lock=lock)
    if state is None:
        state = HaedoriState(
            user_id=user_id, cheer=0, listen=0, playful=0, advice=0, fed_count=0, snacks={}
        )
        db.add(state)
        db.flush()
    return state


def scores_of(state: Optional[HaedoriState]) -> dict[str, int]:
    if state is None:
        return {t: 0 for t in TRAITS}
    return {t: int(getattr(state, t) or 0) for t in TRAITS}


def personality_type(scores: dict[str, int]) -> dict:
    """점수로 성격 이름을 정한다. 동점이면 TRAITS 순서가 앞인 쪽."""
    ranked = sorted(TRAITS, key=lambda t: (-scores.get(t, 0), TRAITS.index(t)))
    primary, secondary = ranked[0], ranked[1]
    top, second = scores.get(primary, 0), scores.get(secondary, 0)

    if top <= 0:
        return {**NEUTRAL_TYPE, "primary": None, "secondary": None}

    info = TRAIT_INFO[primary]
    mixed = second > 0 and second >= top * MIX_RATIO
    if mixed:
        name = f"{TRAIT_INFO[secondary]['adjective']} {info['name']}"
    else:
        name = info["name"]
    return {
        "key": f"{primary}+{secondary}" if mixed else primary,
        "name": f"{name} 해도리",
        "emoji": info["emoji"],
        "description": info["description"],
        "primary": primary,
        "secondary": secondary if mixed else None,
    }


def state_payload(state: Optional[HaedoriState]) -> dict:
    scores = scores_of(state)
    owned = (state.snacks if state else None) or {}
    return {
        "personality": {
            "scores": scores,
            "fed_count": int(state.fed_count or 0) if state else 0,
            "type": personality_type(scores),
            "traits": [
                {
                    "key": t,
                    "name": TRAIT_INFO[t]["name"],
                    "emoji": TRAIT_INFO[t]["emoji"],
                    "description": TRAIT_INFO[t]["description"],
                }
                for t in TRAITS
            ],
        },
        "snacks": [
            {
                "key": key,
                "name": s["name"],
                "emoji": s["emoji"],
                "price": s["price"],
                "effects": s["effects"],
                "story": s["story"],
                "count": int(owned.get(key, 0) or 0),
            }
            for key, s in SNACKS.items()
        ],
    }


# ---------- 사기 / 먹이기 ----------

def buy_snack(db: Session, user_id: int, snack_key: str, quantity: int = 1) -> dict:
    snack = SNACKS.get(snack_key)
    if snack is None:
        raise SnackError("없는 간식이에요", 404)
    if quantity < 1 or quantity > 10:
        raise SnackError("한 번에 1~10개까지 살 수 있어요")

    cost = snack["price"] * quantity
    try:
        deducted = (
            db.query(User)
            .filter(User.id == user_id, User.pearls >= cost)
            .update({User.pearls: User.pearls - cost}, synchronize_session=False)
        )
        if not deducted:
            db.rollback()
            raise SnackError("진주가 부족해요")

        balance = int(db.query(User.pearls).filter(User.id == user_id).scalar() or 0)
        db.add(
            PearlTransaction(
                user_id=user_id,
                amount=-cost,
                reason="snack_buy",
                ref_key=None,
                balance_after=balance,
            )
        )

        state = get_or_create_state(db, user_id, lock=True)
        snacks = dict(state.snacks or {})
        snacks[snack_key] = int(snacks.get(snack_key, 0) or 0) + quantity
        state.snacks = snacks  # JSON 컬럼은 새 dict를 넣어야 변경이 반영된다
        db.commit()
    except SnackError:
        raise
    except Exception:
        db.rollback()
        logger.exception("[SNACK] buy failed user_id=%s snack=%s", user_id, snack_key)
        raise

    logger.info("[SNACK] buy user_id=%s snack=%s x%s balance=%s", user_id, snack_key, quantity, balance)
    db.refresh(state)
    return {"balance": balance, **state_payload(state)}


def feed_snack(db: Session, user_id: int, snack_key: str) -> dict:
    snack = SNACKS.get(snack_key)
    if snack is None:
        raise SnackError("없는 간식이에요", 404)

    try:
        state = get_or_create_state(db, user_id, lock=True)
        snacks = dict(state.snacks or {})
        have = int(snacks.get(snack_key, 0) or 0)
        if have <= 0:
            db.rollback()
            raise SnackError("이 간식이 없어요. 상점에서 사 와야 해요")

        before = personality_type(scores_of(state))
        snacks[snack_key] = have - 1
        state.snacks = snacks
        for trait, value in snack["effects"].items():
            setattr(state, trait, int(getattr(state, trait) or 0) + int(value))
        state.fed_count = int(state.fed_count or 0) + 1
        db.commit()
    except SnackError:
        raise
    except Exception:
        db.rollback()
        logger.exception("[SNACK] feed failed user_id=%s snack=%s", user_id, snack_key)
        raise

    db.refresh(state)
    payload = state_payload(state)
    after = payload["personality"]["type"]
    return {
        **payload,
        "fed": {
            "snack_key": snack_key,
            "reaction": snack["reaction"],
            "gained": [
                {"trait": t, "name": TRAIT_INFO[t]["name"], "emoji": TRAIT_INFO[t]["emoji"], "amount": v}
                for t, v in snack["effects"].items()
            ],
            "type_changed": before["key"] != after["key"],
            "previous_type_name": before["name"],
        },
    }


# ---------- 말투 지시문 (편지·채팅 공용) ----------

def build_personality_prompt(scores: dict[str, int]) -> str:
    """성격 점수 → 시스템 프롬프트 끝에 붙일 말투 지시문. 간식을 안 먹었으면 빈 문자열."""
    ptype = personality_type(scores)
    primary = ptype.get("primary")
    if not primary:
        return ""

    lines = [
        "[해도리의 지금 성격]",
        "위의 형식·금지 규칙은 그대로 지키고, 말투와 태도만 아래 성격을 따른다.",
        TRAIT_INFO[primary]["prompt"],
    ]
    secondary = ptype.get("secondary")
    if secondary:
        lines.append(f"{TRAIT_INFO[secondary]['mix']}.")
    return "\n".join(lines)


def personality_prompt_for_user(db: Session, user_id: int) -> str:
    """실패해도 편지·채팅은 기본 말투로 계속 가야 하므로 예외를 삼킨다."""
    try:
        return build_personality_prompt(scores_of(get_state(db, user_id)))
    except Exception:
        logger.exception("[PERSONALITY] prompt load failed user_id=%s", user_id)
        return ""
