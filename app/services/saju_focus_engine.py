# app/services/saju_focus_engine.py
# 역할:
# - 사주 원국(chart_payload)과 오늘 날짜를 결합해 오늘의 해석 재료를 만든다.
# - 일간 기준으로 오늘 일진이 어떤 십성 흐름인지 계산한다.
# - 강한 오행/약한 오행을 행동 조언으로 변환한다.
# - category_guides를 relation 고정 문장이 아니라 relation + dominant/weak 오행 보정으로 생성한다.
# - LLM이 범용 운세를 쓰지 않도록 사람별로 다른 focus_points를 제공한다.

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from app.services.saju_chart_engine import build_day_pillar


ELEMENT_KO = ["목", "화", "토", "금", "수"]

GENERATES = {
    "목": "화",
    "화": "토",
    "토": "금",
    "금": "수",
    "수": "목",
}

CONTROLS = {
    "목": "토",
    "화": "금",
    "토": "수",
    "금": "목",
    "수": "화",
}


RELATION_HINTS = {
    "self": {
        "label": "비견/겁재",
        "theme": "자기 기준과 선택",
        "direction": "남의 흐름에 끌려가기보다 본인의 판단선을 분명히 잡는 편이 좋은 때로 읽힙니다.",
        "core": "자기 기준이 강해지는 만큼 비교심이나 고집으로 흐르지 않도록 조절하는 것이 중요해 보입니다.",
        "work_study": "일이나 공부에서는 자신의 방식이 또렷해질 수 있어, 먼저 할 일과 나중에 볼 일을 분리하는 쪽이 어울립니다.",
        "relationship": "인간관계에서는 의견을 또렷하게 말하되, 상대를 바로 설득하려 하기보다 차이를 인정하는 태도가 필요해 보입니다.",
        "emotion": "감정 흐름은 자존심이 건드려질 때 반응이 빨라질 수 있으니, 바로 답하기보다 문장을 한 번 고르는 편이 좋습니다.",
        "love": "연애나 가까운 관계에서는 주도권을 확인하려 하기보다 서로의 속도를 맞추는 쪽이 편안하게 이어질 수 있습니다.",
        "money": "금전적으로는 본인의 판단을 믿되, 필요성과 만족감을 따로 구분해서 보는 편이 좋습니다.",
        "condition": "컨디션은 의욕이 앞서면 몸의 신호를 놓치기 쉬우니, 오래 붙잡기보다 짧게 끊어가는 방식이 맞아 보입니다.",
    },
    "output": {
        "label": "식상",
        "theme": "표현과 실행",
        "direction": "생각을 안에만 두기보다 작게라도 밖으로 꺼내보는 편이 좋은 때로 읽힙니다.",
        "core": "머릿속에 머무는 아이디어를 말, 글, 작업물로 바꾸는 과정이 중요해 보입니다.",
        "work_study": "일이나 공부에서는 정리한 내용을 직접 써보거나 설명해볼 때 흐름이 잡히기 쉬워 보입니다.",
        "relationship": "인간관계에서는 말이 많아질 수 있으니, 전달하고 싶은 핵심을 짧게 남기는 방식이 좋습니다.",
        "emotion": "감정 흐름은 쌓아두면 답답해질 수 있어, 안전한 기록이나 대화로 풀어내는 편이 도움이 됩니다.",
        "love": "연애나 가까운 관계에서는 마음을 숨기기보다 부담 없는 표현으로 분위기를 열어보는 쪽이 어울립니다.",
        "money": "금전적으로는 하고 싶은 선택지가 늘 수 있으니, 지금 꼭 필요한 것과 나중에 해도 되는 것을 나눠보는 편이 좋습니다.",
        "condition": "컨디션은 활동량이 늘기 쉬워, 한 번에 오래 몰아가기보다 중간중간 호흡을 나누는 방식이 맞아 보입니다.",
    },
    "wealth": {
        "label": "재성",
        "theme": "현실 판단과 결과",
        "direction": "눈에 보이는 결과와 실제 쓸모를 기준으로 움직이는 편이 좋은 때로 읽힙니다.",
        "core": "생각보다 현실적인 기준이 중요해지는 날이라, 감정보다 결과와 필요성을 함께 보는 태도가 필요해 보입니다.",
        "work_study": "일이나 공부에서는 추상적인 고민보다 제출물, 점수, 마감처럼 확인 가능한 결과에 가까운 일부터 잡는 편이 좋습니다.",
        "relationship": "인간관계에서는 상대의 말보다 실제 태도를 보려는 마음이 커질 수 있어, 너무 차갑게 보이지 않도록 표현을 조절하면 좋습니다.",
        "emotion": "감정 흐름은 원하는 결과가 바로 보이지 않을 때 조급해질 수 있으니, 작은 진전도 확인하는 편이 좋습니다.",
        "love": "연애나 가까운 관계에서는 말보다 행동을 보게 되는 흐름이라, 상대의 태도를 천천히 관찰하는 쪽이 어울립니다.",
        "money": "금전적으로는 만족감보다 실속을 먼저 보는 편이 맞고, 결제 전 사용 빈도를 떠올려보는 것이 도움이 됩니다.",
        "condition": "컨디션은 해야 할 일이 많아지면 몸이 굳기 쉬워, 움직임을 작게라도 넣어주는 편이 좋습니다.",
    },
    "pressure": {
        "label": "관성",
        "theme": "책임과 질서",
        "direction": "해야 할 일을 피하기보다 작게 나누어 정리하는 편이 좋은 때로 읽힙니다.",
        "core": "외부 기준이나 책임이 크게 느껴질 수 있어, 완벽하게 버티기보다 감당 가능한 순서를 세우는 것이 중요해 보입니다.",
        "work_study": "일이나 공부에서는 평가, 규칙, 마감처럼 정해진 기준을 먼저 확인하고 움직이는 쪽이 안정적으로 이어질 수 있습니다.",
        "relationship": "인간관계에서는 상대의 기대를 많이 의식할 수 있으니, 가능한 범위를 미리 말해두는 편이 좋습니다.",
        "emotion": "감정 흐름은 부담이 커질수록 스스로를 몰아붙이기 쉬워, 오늘 처리할 몫을 현실적으로 낮추는 태도가 필요해 보입니다.",
        "love": "연애나 가까운 관계에서는 책임 있게 대하려는 마음이 커질 수 있지만, 지나친 눈치 보기로 흐르지 않게 조심하면 좋습니다.",
        "money": "금전적으로는 계획 없이 움직이기보다 정해둔 범위 안에서 선택하는 방식이 어울립니다.",
        "condition": "컨디션은 긴장이 쌓이면 어깨나 목처럼 특정 부위가 뻣뻣해질 수 있어, 짧게 풀어주는 루틴이 도움이 됩니다.",
    },
    "support": {
        "label": "인성",
        "theme": "흡수와 정리",
        "direction": "밖으로 밀어붙이기보다 이해하고 정돈하는 편이 좋은 때로 읽힙니다.",
        "core": "새로운 확장보다 받아들이고 소화하는 힘이 중요해지는 날이라, 판단을 늦추고 자료를 정리하는 태도가 좋아 보입니다.",
        "work_study": "일이나 공부에서는 새 과제를 벌이기보다 이미 가진 자료를 다시 읽고 구조화할 때 도움이 될 수 있습니다.",
        "relationship": "인간관계에서는 바로 반응하기보다 상대의 말을 끝까지 듣는 쪽이 오해를 줄이는 데 좋아 보입니다.",
        "emotion": "감정 흐름은 생각이 깊어질 수 있어, 결론을 내리기보다 관찰한 내용을 적어두는 방식이 어울립니다.",
        "love": "연애나 가까운 관계에서는 빠른 확인보다 편안함과 신뢰감을 천천히 살피는 쪽이 좋습니다.",
        "money": "금전적으로는 큰 움직임보다 정보를 모으고 비교하는 태도가 잘 맞아 보입니다.",
        "condition": "컨디션은 조용히 재정비하는 시간이 필요할 수 있어, 혼자 정리할 짧은 틈을 확보하는 편이 좋습니다.",
    },
}


ELEMENT_STYLE = {
    "목": "방향을 넓히고 가능성을 찾으려는 성향",
    "화": "반응이 빠르고 존재감을 드러내려는 성향",
    "토": "현실을 붙잡고 중심을 세우려는 성향",
    "금": "기준을 세우고 불필요한 것을 덜어내려는 성향",
    "수": "흐름을 읽고 깊이 생각하려는 성향",
}


WEAK_ELEMENT_GUIDES = {
    "목": "방향을 먼저 정해두면 흐름이 흩어지는 것을 줄일 수 있어 보입니다.",
    "화": "필요한 말이나 반응을 너무 미루지 않고 짧게 드러내는 것이 보완점으로 보입니다.",
    "토": "일의 순서와 기준을 적어두면 흔들림을 줄이는 데 도움이 될 수 있습니다.",
    "금": "선택 기준을 두세 개로 좁히면 결정을 미루는 흐름을 줄일 수 있어 보입니다.",
    "수": "생각이 길어질 때는 자료를 더 찾기보다 지금 아는 내용을 정리하는 것이 좋아 보입니다.",
}

STRONG_ELEMENT_WARNINGS = {
    "목": "확장하려는 마음이 커질수록 마무리가 흐려지지 않게 범위를 좁히는 태도가 필요해 보입니다.",
    "화": "반응이 빨라질수록 말과 행동이 앞서가지 않도록 잠깐 멈추는 장치가 필요해 보입니다.",
    "토": "붙잡고 정리하려는 마음이 강할수록 변화에 너무 늦게 반응하지 않도록 살피는 편이 좋습니다.",
    "금": "기준이 강해질수록 스스로와 타인에게 지나치게 엄격해지지 않도록 여지를 남기는 편이 좋습니다.",
    "수": "생각이 깊어질수록 실행이 늦어지지 않게 작게 움직이는 장치가 필요해 보입니다.",
}


CATEGORY_ADJUSTMENTS = {
    "목": {
        "work_study": "일이나 공부에서는 새 범위를 넓히기보다 오늘 끝낼 단위를 작게 잡는 편이 좋습니다.",
        "relationship": "관계에서는 하고 싶은 말을 모두 꺼내기보다 상대가 받아들일 수 있는 순서로 나누는 태도가 어울립니다.",
        "emotion": "마음이 앞서갈 때는 지금 실제로 가능한 행동 하나를 정해두는 것이 도움이 됩니다.",
        "love": "가까운 관계에서는 기대를 크게 키우기보다 오늘 나눌 수 있는 작은 대화에 집중하는 편이 좋습니다.",
        "money": "금전 판단에서는 새로운 선택지를 늘리기보다 이미 생각해둔 항목의 필요성을 다시 보는 쪽이 맞아 보입니다.",
        "condition": "컨디션은 들뜬 흐름이 길어지지 않도록 짧은 정리 시간을 끼워 넣는 편이 좋습니다.",
    },
    "화": {
        "work_study": "일이나 공부에서는 속도를 내기 전에 검토 기준을 먼저 세우는 편이 실수를 줄이는 데 좋아 보입니다.",
        "relationship": "관계에서는 즉각적인 반응보다 말의 온도를 낮춰 전달하는 태도가 도움이 됩니다.",
        "emotion": "마음의 반응이 빠르게 바뀔 수 있어, 바로 표현하기보다 한 번 적어본 뒤 정리하는 편이 좋습니다.",
        "love": "가까운 관계에서는 애정 표현이 앞서가기보다 상대의 상태를 살핀 뒤 움직이는 쪽이 자연스럽습니다.",
        "money": "금전 판단에서는 끌리는 마음이 생겨도 결제 전 사용 장면을 구체적으로 떠올려보는 편이 좋습니다.",
        "condition": "컨디션은 열이 한쪽으로 몰리지 않도록 오래 몰입하기보다 짧게 끊어가는 방식이 어울립니다.",
    },
    "토": {
        "work_study": "일이나 공부에서는 붙잡고 있는 일을 오래 끌기보다 완료 기준을 정해두는 편이 좋습니다.",
        "relationship": "관계에서는 익숙한 방식만 고집하기보다 상대의 변화 신호를 살피는 태도가 필요해 보입니다.",
        "emotion": "마음이 답답하게 뭉칠 수 있으니, 문제를 머릿속에만 두기보다 목록으로 분리하는 편이 좋습니다.",
        "love": "가까운 관계에서는 확인받고 싶은 마음이 커질 수 있어, 요구보다 설명의 형태로 전하는 것이 좋습니다.",
        "money": "금전 판단에서는 보유와 유지에 치우치기보다 지금 실제로 필요한지를 확인하는 편이 좋습니다.",
        "condition": "컨디션은 몸이 무겁게 느껴질 수 있어, 자리를 바꾸거나 가볍게 움직이며 흐름을 풀어주는 것이 좋습니다.",
    },
    "금": {
        "work_study": "일이나 공부에서는 완성도를 높이려다 시작이 늦어지지 않도록 초안을 먼저 만드는 편이 좋습니다.",
        "relationship": "관계에서는 판단이 빨라질 수 있어, 상대의 의도를 단정하기보다 한 번 더 확인하는 태도가 어울립니다.",
        "emotion": "마음이 날카롭게 정리될 수 있으니, 스스로에게도 너무 엄격한 기준을 적용하지 않는 편이 좋습니다.",
        "love": "가까운 관계에서는 맞고 틀림보다 서로의 입장을 확인하는 쪽이 관계 흐름을 부드럽게 만듭니다.",
        "money": "금전 판단에서는 불필요한 것을 덜어내는 감각이 살아날 수 있어, 항목별로 우선순위를 나누는 편이 좋습니다.",
        "condition": "컨디션은 긴장감이 특정 부위에 쌓이지 않도록 자세를 자주 바꾸는 것이 도움이 됩니다.",
    },
    "수": {
        "work_study": "일이나 공부에서는 자료 탐색이 길어질 수 있어, 찾는 시간과 정리하는 시간을 나누는 편이 좋습니다.",
        "relationship": "관계에서는 혼자 추측하는 시간이 길어지지 않도록 필요한 부분만 차분히 확인하는 태도가 좋습니다.",
        "emotion": "생각이 깊어질수록 감정이 커 보일 수 있으니, 사실과 느낌을 따로 적어보는 방식이 어울립니다.",
        "love": "가까운 관계에서는 마음속 결론을 먼저 내리기보다 상대의 실제 표현을 기다려보는 편이 좋습니다.",
        "money": "금전 판단에서는 정보를 더 모으는 것보다 비교 기준을 정해두는 쪽이 도움이 됩니다.",
        "condition": "컨디션은 머릿속 긴장이 길어지지 않도록 짧은 움직임으로 흐름을 끊어주는 편이 좋습니다.",
    },
}


def _get_counts(chart_payload: Dict[str, Any]) -> Dict[str, float]:
    summary = chart_payload.get("elementSummary") or {}
    counts = summary.get("counts") or {}

    return {
        element: float(counts.get(element, 0) or 0)
        for element in ELEMENT_KO
    }


def _get_day_master_element(chart_payload: Dict[str, Any]) -> Optional[str]:
    day_master = chart_payload.get("dayMaster") or {}
    element = day_master.get("element")

    if element in ELEMENT_KO:
        return element

    return None


def _get_day_master_stem(chart_payload: Dict[str, Any]) -> Optional[str]:
    day_master = chart_payload.get("dayMaster") or {}
    stem = day_master.get("stem")

    if isinstance(stem, str) and stem.strip():
        return stem.strip()

    return None


def _season_element(target_date: date) -> str:
    month = target_date.month

    if month in (3, 4, 5):
        return "목"
    if month in (6, 7, 8):
        return "화"
    if month in (9, 10):
        return "금"
    if month in (11, 12, 1):
        return "수"

    return "토"


def _relation_from_day_master(
    day_master_element: Optional[str],
    today_element: str,
) -> str:
    if day_master_element not in ELEMENT_KO:
        return "support"

    if today_element == day_master_element:
        return "self"

    if GENERATES.get(day_master_element) == today_element:
        return "output"

    if CONTROLS.get(day_master_element) == today_element:
        return "wealth"

    if CONTROLS.get(today_element) == day_master_element:
        return "pressure"

    return "support"


def _pick_today_main_element(today_pillar: Dict[str, Any], season_element: str) -> str:
    stem_element = (today_pillar.get("stem_element") or {}).get("element")
    branch_element = (today_pillar.get("branch_element") or {}).get("element")

    if stem_element in ELEMENT_KO:
        return stem_element

    if branch_element in ELEMENT_KO:
        return branch_element

    return season_element


def _element_balance_message(
    counts: Dict[str, float],
    dominant_element: Optional[str],
    weak_element: Optional[str],
) -> str:
    if not counts or dominant_element is None or weak_element is None:
        return "오행 분포는 큰 흐름 중심으로 참고하는 편이 좋아 보입니다."

    dominant_value = counts.get(dominant_element, 0)
    weak_value = counts.get(weak_element, 0)
    gap = dominant_value - weak_value

    strong_msg = STRONG_ELEMENT_WARNINGS.get(dominant_element, "")
    weak_msg = WEAK_ELEMENT_GUIDES.get(weak_element, "")

    if gap >= 3:
        return (
            f"원국에서는 {dominant_element} 기운이 비교적 두드러지고 "
            f"{weak_element} 기운은 약하게 잡힙니다. "
            f"{strong_msg} {weak_msg}"
        ).strip()

    return (
        f"원국에서는 {dominant_element} 기운이 조금 더 드러나며, "
        f"{weak_element} 쪽은 의식적으로 보완하면 좋게 읽힙니다. "
        f"{weak_msg}"
    ).strip()


def _build_main_keywords(
    relation_theme: str,
    dominant_element: Optional[str],
    weak_element: Optional[str],
) -> list[str]:
    keywords = [relation_theme]

    if dominant_element:
        keywords.append(f"{dominant_element} 과다 조절")

    if weak_element:
        keywords.append(f"{weak_element} 보완")

    return keywords


def _build_personalized_summary(
    day_master_stem: Optional[str],
    day_master_element: Optional[str],
    today_ganji: str,
    today_element: str,
    relation_label: str,
    relation_direction: str,
    dominant_element: Optional[str],
    weak_element: Optional[str],
    balance_message: str,
) -> str:
    day_master_text = f"{day_master_stem or ''}{day_master_element or ''}".strip()

    strong_msg = STRONG_ELEMENT_WARNINGS.get(dominant_element or "", "")
    weak_msg = WEAK_ELEMENT_GUIDES.get(weak_element or "", "")

    return (
        f"오늘 일진은 {today_ganji}이며, 오늘의 중심 오행은 {today_element}로 봅니다. "
        f"{day_master_text} 일간에게는 {relation_label} 흐름으로 작용해 {relation_direction} "
        f"{balance_message} {strong_msg} {weak_msg}"
    ).strip()


def _merge_category_guide(
    base_text: str,
    category: str,
    dominant_element: Optional[str],
    weak_element: Optional[str],
) -> str:
    """
    relation 기반 기본 문장에 강한 오행/약한 오행의 카테고리별 보정을 섞는다.
    같은 relation이어도 dominant/weak가 다르면 서로 다른 가이드가 나오도록 만든다.
    """

    dominant_adjustment = ""
    weak_adjustment = ""

    if dominant_element in CATEGORY_ADJUSTMENTS:
        dominant_adjustment = CATEGORY_ADJUSTMENTS[dominant_element].get(category, "")

    if weak_element in CATEGORY_ADJUSTMENTS:
        weak_adjustment = CATEGORY_ADJUSTMENTS[weak_element].get(category, "")

    parts = [base_text]

    if dominant_adjustment:
        parts.append(f"강한 {dominant_element} 흐름을 고려하면, {dominant_adjustment}")

    if weak_adjustment and weak_adjustment != dominant_adjustment:
        parts.append(f"부족한 {weak_element} 쪽을 보완하려면, {weak_adjustment}")

    return " ".join(part for part in parts if part).strip()


def _build_category_guides(
    relation_hint: Dict[str, str],
    dominant_element: Optional[str],
    weak_element: Optional[str],
) -> Dict[str, str]:
    return {
        "work_study": _merge_category_guide(
            relation_hint["work_study"],
            "work_study",
            dominant_element,
            weak_element,
        ),
        "relationship": _merge_category_guide(
            relation_hint["relationship"],
            "relationship",
            dominant_element,
            weak_element,
        ),
        "emotion": _merge_category_guide(
            relation_hint["emotion"],
            "emotion",
            dominant_element,
            weak_element,
        ),
        "love": _merge_category_guide(
            relation_hint["love"],
            "love",
            dominant_element,
            weak_element,
        ),
        "money": _merge_category_guide(
            relation_hint["money"],
            "money",
            dominant_element,
            weak_element,
        ),
        "condition": _merge_category_guide(
            relation_hint["condition"],
            "condition",
            dominant_element,
            weak_element,
        ),
    }


def build_saju_focus_points(
    chart_payload: Dict[str, Any],
    target_date: date,
) -> Dict[str, Any]:
    counts = _get_counts(chart_payload)
    day_master_element = _get_day_master_element(chart_payload)
    day_master_stem = _get_day_master_stem(chart_payload)

    today_pillar = build_day_pillar(target_date)
    season_element = _season_element(target_date)
    today_element = _pick_today_main_element(today_pillar, season_element)

    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    dominant_element = sorted_counts[0][0] if sorted_counts else None
    weak_element = sorted_counts[-1][0] if sorted_counts else None

    relation_key = _relation_from_day_master(day_master_element, today_element)
    relation_hint = RELATION_HINTS[relation_key]

    day_master_style = ELEMENT_STYLE.get(
        day_master_element,
        "자신의 기준을 중심으로 하루 흐름을 받아들이는 성향",
    )

    balance_message = _element_balance_message(
        counts=counts,
        dominant_element=dominant_element,
        weak_element=weak_element,
    )

    main_keywords = _build_main_keywords(
        relation_theme=relation_hint["theme"],
        dominant_element=dominant_element,
        weak_element=weak_element,
    )

    today_ganji = today_pillar.get("ganji") or ""
    today_stem = today_pillar.get("stem") or ""
    today_branch = today_pillar.get("branch") or ""

    summary = _build_personalized_summary(
        day_master_stem=day_master_stem,
        day_master_element=day_master_element,
        today_ganji=today_ganji,
        today_element=today_element,
        relation_label=relation_hint["label"],
        relation_direction=relation_hint["direction"],
        dominant_element=dominant_element,
        weak_element=weak_element,
        balance_message=balance_message,
    )

    category_guides = _build_category_guides(
        relation_hint=relation_hint,
        dominant_element=dominant_element,
        weak_element=weak_element,
    )

    return {
        "main_keywords": main_keywords,
        "relation": {
            "key": relation_key,
            "label": relation_hint["label"],
            "theme": relation_hint["theme"],
            "day_master_element": day_master_element,
            "day_master_stem": day_master_stem,
            "today_element": today_element,
            "today_ganji": today_ganji,
            "today_stem": today_stem,
            "today_branch": today_branch,
        },
        "today_pillar": today_pillar,
        "dominant_element": dominant_element,
        "weak_element": weak_element,
        "day_master_element": day_master_element,
        "day_master_stem": day_master_stem,
        "day_master_style": day_master_style,
        "today_element": today_element,
        "season_element": season_element,
        "summary": summary,
        "core_reason": relation_hint["core"],
        "category_guides": category_guides,
        "element_counts": counts,
        "balance_message": balance_message,
        "weak_element_guide": WEAK_ELEMENT_GUIDES.get(weak_element or "", ""),
        "strong_element_warning": STRONG_ELEMENT_WARNINGS.get(dominant_element or "", ""),
    }