from typing import Dict, Optional

from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune
from app.services.prompt_templates import (
    letter_system_prompt,
    build_letter_user_prompt,
)


def generate_otter_letter(
    user: User,
    diary_entry: DiaryEntry,
    fortune: Optional[DailyFortune],
) -> Dict:
    """
    반환:
    {
      "content": "...",
      "element_hint": {...},
      "model": "..."
    }
    """

    fortune_hint = ""
    element_hint = None

    if fortune and fortune.element_hint:
        fortune_hint = fortune.element_hint.get("message", "")
        element_hint = fortune.element_hint

    # 🦦 지금은 수달 톤의 룰 기반 편지
    content = (
        "오늘 하루가 쉽지 않았던 게 느껴져.\n\n"
        "해야 할 게 많았는데 마음이 따라주지 않았을 수도 있어.\n"
        "그렇다고 오늘이 의미 없던 하루는 아니야.\n\n"
        "지금은 더 잘하려 애쓰기보다,\n"
        "오늘을 여기까지 버텨온 너를 인정해줘도 괜찮은 날 같아."
    )

    return {
        "content": content,
        "element_hint": element_hint,
        "model": "rule-based-letter-v1",
    }
