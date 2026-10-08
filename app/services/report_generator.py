from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.core.config import settings
from app.services.letter_llm_service import LetterLLMError, request_letter_llm

logger = logging.getLogger(__name__)


def build_monthly_system_prompt() -> str:
    return (
        "너는 '해도리'라는 다정한 수달 캐릭터다.\n"
        "사용자가 한 달 동안 남긴 감정 기록과 일기를 읽고, 편지를 쓴다.\n"
        "\n"
        "[반드시 지킬 출력 형식]\n"
        "아래 JSON 형식으로만 출력한다. 설명, 마크다운, 코드블록 표시는 절대 붙이지 않는다.\n"
        '{"insights": ["...", "...", "..."], "summary": "...", '
        '"highlights": ["...", "...", "..."], "comment": "..."}\n'
        "\n"
        "[insights — 감정 기록을 보고 쓰는 편지]\n"
        "- 3개의 문단. 각 문단은 2~3문장.\n"
        "- 존댓말. 실제로 편지를 쓰듯 자연스럽게 이어서 쓴다.\n"
        "- 1문단: 이번 달 감정의 큰 결. 어떤 감정이 많았고 어떻게 오갔는지.\n"
        "- 2문단: 눈에 띄는 패턴 하나. 회복 속도, 특정 요일, 지난달과의 차이 중 "
        "가장 얘기할 거리가 있는 것 하나만 고른다.\n"
        "- 3문단: 기록 습관에서 인상적인 점. 연속으로 쓴 구간이나 기록의 리듬.\n"
        "- 관찰한 것을 말하고, 궁금한 것은 물어본다.\n"
        "\n"
        "[summary — 이번 달 요약]\n"
        "- 2~3문장. 존댓말.\n"
        "\n"
        "[highlights — 이번 달 대표적인 순간 3개]\n"
        "- 각 항목은 한 문장, 20자 내외로 짧게.\n"
        "- 실제 일기 내용에 근거해서 쓴다.\n"
        "\n"
        "[comment — 한 달을 돌아보는 코멘트]\n"
        "- 3~4문장. 존댓말.\n"
        "- insights와 내용이 겹치지 않게, 일기에 담긴 이야기 쪽에 집중한다.\n"
        "\n"
        "[절대 금지]\n"
        "- 반드시 한국어로만 작성한다.\n"
        "- '괜찮아요', '충분해요', '자연스러운 거예요' 같은 상투적인 위로 문구를 쓰지 않는다.\n"
        "- 기록률, 퍼센트, 통계 수치를 나열하지 않는다.\n"
        "- 훈계하거나 진단하지 않는다.\n"
        "- 일기에 없는 사실을 지어내지 않는다.\n"
        "- JSON 외의 텍스트를 절대 출력하지 않는다.\n"
    )


def build_monthly_user_prompt(
    year: int,
    month: int,
    mood_counts: list[dict],
    day_summaries: list[dict],
    stats: Optional[dict] = None,
) -> str:
    mood_text = ", ".join(f"{m['label']} {m['count']}일" for m in mood_counts) or "기록 없음"

    lines = []
    for item in day_summaries:
        tag = item.get("summary_tag") or ""
        preview = (item.get("content") or "").strip().replace("\n", " ")
        if len(preview) > 100:
            preview = preview[:100] + "..."
        lines.append(f"- {item['date']} ({item['label']}) {tag} {preview}".strip())

    diary_text = "\n".join(lines) if lines else "- 기록 없음"

    stat_lines = []
    if stats:
        if stats.get("recorded_days") is not None:
            stat_lines.append(
                f"- 기록한 날: {stats['total_days']}일 중 {stats['recorded_days']}일"
            )
        if stats.get("longest_streak", 0) >= 3:
            stat_lines.append(f"- 가장 길게 연속으로 기록한 구간: {stats['longest_streak']}일")
        if stats.get("avg_recovery") is not None:
            stat_lines.append(
                f"- 지친 기록 이후 다시 편안한 기록까지 평균 {stats['avg_recovery']}일"
            )
        if stats.get("hard_weekday"):
            stat_lines.append(
                f"- 지친 기록이 가장 잦았던 요일: {stats['hard_weekday']}요일 "
                f"({stats['hard_weekday_count']}번)"
            )
        if stats.get("prev_month_diff"):
            stat_lines.append(f"- 지난달과 비교: {stats['prev_month_diff']}")

    stat_text = "\n".join(stat_lines) if stat_lines else "- 특이사항 없음"

    return (
        f"{year}년 {month}월 편지를 써줘.\n\n"
        f"감정 분포: {mood_text}\n\n"
        f"관찰된 패턴:\n{stat_text}\n\n"
        f"일기 목록:\n{diary_text}\n\n"
        "위 내용을 바탕으로 JSON 형식으로만 응답해줘."
    )


def parse_llm_json(text: str) -> Optional[dict]:
    if not text:
        return None

    cleaned = re.sub(r"```(?:json)?", "", text).strip()

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("[MONTHLY_REPORT] json parse failed text=%s", cleaned[:300])
        return None

    if not isinstance(data, dict):
        return None

    summary = data.get("summary")
    highlights = data.get("highlights")
    comment = data.get("comment")
    insights = data.get("insights")

    if not isinstance(summary, str) or not summary.strip():
        return None
    if not isinstance(comment, str) or not comment.strip():
        return None
    if not isinstance(highlights, list):
        return None
    if not isinstance(insights, list):
        return None

    clean_highlights = [h.strip() for h in highlights if isinstance(h, str) and h.strip()]
    clean_insights = [p.strip() for p in insights if isinstance(p, str) and p.strip()]

    if not clean_highlights or not clean_insights:
        return None

    return {
        "insights": clean_insights[:4],
        "summary": summary.strip(),
        "highlights": clean_highlights[:3],
        "comment": comment.strip(),
    }


async def generate_monthly_report(
    year: int,
    month: int,
    mood_counts: list[dict],
    day_summaries: list[dict],
    stats: Optional[dict] = None,
) -> tuple[dict, str, Optional[str]]:
    """
    returns: (report_dict, source_type, model_name)
    """
    model = (
        getattr(settings, "SUMMARY_LLM_MODEL", None)
        or getattr(settings, "LLM_MODEL", None)
        or "dori-diary-deploy"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": build_monthly_system_prompt()},
            {
                "role": "user",
                "content": build_monthly_user_prompt(
                    year, month, mood_counts, day_summaries, stats
                ),
            },
        ],
        "temperature": 0.85,
        "max_tokens": 1600,
    }

    try:
        result = await request_letter_llm(payload)
        parsed = parse_llm_json(result.get("content") or "")

        if parsed:
            return parsed, "llm", result.get("model") or model

        logger.warning("[MONTHLY_REPORT] llm response unusable, falling back")

    except LetterLLMError as e:
        logger.warning("[MONTHLY_REPORT] llm failed error=%s", str(e))

    return (
        build_fallback_report(year, month, mood_counts, day_summaries, stats),
        "fallback",
        None,
    )


def build_fallback_report(
    year: int,
    month: int,
    mood_counts: list[dict],
    day_summaries: list[dict],
    stats: Optional[dict] = None,
) -> dict:
    if not mood_counts:
        return {
            "insights": [
                f"{month}월은 아직 비어 있네요. "
                "오늘 어땠는지 한 줄만 남겨두면 다음 달엔 돌아볼 게 생겨요."
            ],
            "summary": f"{month}월은 아직 기록이 없어요.",
            "highlights": ["첫 일기를 기다리고 있어요"],
            "comment": "부담 갖지 말고 편하게 시작해보세요.",
        }

    top = mood_counts[0]
    recorded = len(day_summaries)
    stats = stats or {}

    paragraphs = [
        f"{month}월엔 '{top['label']}' 감정인 날이 {top['count']}일로 가장 많았어요."
    ]

    if stats.get("avg_recovery") is not None and stats["avg_recovery"] <= 2:
        paragraphs.append(
            "지친 기록 다음엔 대체로 금방 편안한 쪽으로 돌아오셨어요. "
            "무너져도 제자리를 찾는 편인 것 같아요."
        )
    elif stats.get("hard_weekday"):
        paragraphs.append(
            f"{stats['hard_weekday']}요일이 유난히 버거우셨던 것 같아요. "
            "그 요일엔 미리 여유를 조금 만들어두시면 어떨까요."
        )

    if stats.get("longest_streak", 0) >= 3:
        paragraphs.append(
            f"{stats['longest_streak']}일을 내리 쓰신 구간이 있었어요. "
            "그 무렵엔 적어두고 싶은 게 많으셨나 봐요."
        )

    highlights = []
    seen = set()
    for item in day_summaries:
        tag = (item.get("summary_tag") or "").strip()
        if tag and tag not in seen:
            seen.add(tag)
            highlights.append(f"{item['date'][-2:]}일 {tag}")
        if len(highlights) >= 3:
            break

    if not highlights:
        highlights = [f"{item['date'][-2:]}일 {item['label']}" for item in day_summaries[:3]]

    return {
        "insights": paragraphs,
        "summary": (
            f"{month}월에는 {recorded}일을 기록했고, "
            f"'{top['label']}' 감정인 날이 {top['count']}일로 가장 많았어요."
        ),
        "highlights": highlights,
        "comment": (
            f"이번 달의 중심엔 '{top['label']}'이 있었네요. "
            "다음 달에도 지금처럼 편하게 적어보세요."
        ),
    }