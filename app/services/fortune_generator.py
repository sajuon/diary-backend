from datetime import date
from typing import Dict, Optional

from app.models.user import User
from app.models.profile import UserBirthProfile
from app.services.saju_engine import analyze_daily_element_flow


def generate_daily_fortune(
    user: User,
    profile: Optional[UserBirthProfile],
    fortune_date: date,
) -> Dict:
    """
    반환 값은 그대로 DB에 저장됨
    """

    flow = analyze_daily_element_flow(profile, fortune_date)
    dominant = flow.get("dominant")

    # 🔹 아주 단순한 예시 문장 (나중에 LLM로 대체)
    love = "사소한 말에 마음이 흔들릴 수 있어요."
    study = "집중이 잘 안 되더라도 자책하지 마세요."
    caution = "오늘은 스스로를 몰아붙이지 않는 게 좋아요."
    good_thing = "의외로 작은 위로를 받을 수 있어요."
    ritual = "잠깐 숨을 고르고 물 한 잔 마셔보세요."

    return {
        "love": love,
        "study": study,
        "caution": caution,
        "good_thing": good_thing,
        "ritual": ritual,
        "element_hint": {
            "dominant": dominant,
            "message": flow.get("message"),
        },
        "model": "rule-based-v1",
    }
