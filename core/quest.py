"""한국사 객관식 퀘스트 — 사료 카드 1건에서 4지선다 문제를 생성.

사용 방식:
    card = pick_card(theme="경주")
    q = generate_question(card, language="ko")
    # q = {"question", "options"[4], "correct_idx", "explanation", "card_id"}
"""
from __future__ import annotations

import json
import random
from typing import Any

from core.llm import get_client, DEFAULT_MODEL
from core.rag import SourceCard, load_corpus


QUEST_SYSTEM = """당신은 한국사 객관식 출제관입니다.
주어진 사료 1건만을 근거로 객관식 문제 1개를 JSON 형식으로 만드십시오.

# 출제 원칙 (절대 준수)
1. 질문과 정답은 **사료에 명시된 사실**(인물·연·월·일·장소·사건·관련 인물)에서만 도출.
2. 선지 4개:
   - 1개는 사료에 명시된 **정답**
   - 3개는 **그럴듯한 오답** (같은 시대 인물·비슷한 사건·인접 장소 등 헷갈리기 쉬운 항목)
3. correct_idx — 정답이 위치한 인덱스 (0~3 중 무작위 배치)
4. explanation — 5~8문장으로 사건 배경·인물·장소·의의를 풀어 설명.
   - 어려운 한자어는 괄호로 풀이 (예: "이어(移御, 임금이 거처를 옮김)")
   - 본문 안에 사료 id를 [card_id] 형태로 1~2번 인라인 마커
   - 끝에 짧게 _「출처: 〈사료 제목〉 [card_id]」_

# 학설이 갈리는 사안
사료 summary에 "학설", "다른 견해", "후대에 더해진 설" 등이 있으면 explanation에 양측을 짧게 소개.

# 출력 형식
다음 JSON만 출력 (다른 텍스트·코드펜스 절대 금지):
{
  "question": "질문 문장",
  "options": ["선지A", "선지B", "선지C", "선지D"],
  "correct_idx": 0,
  "explanation": "상세 해설 (5~8문장)"
}"""


_LANG_MAP = {
    "ko": "한국어",
    "en": "English",
    "ja": "日本語",
    "zh": "中文 (简体)",
}


def generate_question(
    card: SourceCard,
    language: str = "ko",
    mode: str = "일반",
) -> dict[str, Any]:
    """사료 카드 한 건으로 객관식 문제 1개 생성. 실패 시 안전한 fallback 반환."""
    client = get_client()
    lang_name = _LANG_MAP.get(language, "한국어")

    family_hint = (
        "응답 톤: 만 8세 이상 가족용. 어휘는 쉽게, 문장은 짧게."
        if mode and mode.startswith("가족")
        else ""
    )

    user_msg = (
        f"[사료]\n"
        f"id: {card.id}\n"
        f"title: {card.title}\n"
        f"date: {card.date}\n"
        f"era: {card.era}\n"
        f"place: {card.place}\n"
        f"original_text: {card.original_text}\n"
        f"summary: {card.summary}\n"
        f"easy_explanation: {card.easy_explanation}\n"
        f"related_persons: {', '.join(card.related_persons)}\n\n"
        f"[응답 언어] {lang_name}로 작성. 단, 사료 id 마커는 [{card.id}] 그대로.\n"
        f"{family_hint}"
    )

    try:
        resp = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1200,
            temperature=0.4,
            system=QUEST_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text.strip()
        # 안전망: 코드펜스 제거
        if text.startswith("```"):
            inner = text.split("```")
            for chunk in inner:
                chunk = chunk.strip()
                if chunk.startswith("{"):
                    text = chunk
                    break
                if chunk.startswith("json"):
                    text = chunk[4:].strip()
                    break

        data = json.loads(text)
        # 검증
        opts = data.get("options", [])
        if not (
            isinstance(data.get("question"), str)
            and isinstance(opts, list) and len(opts) == 4
            and isinstance(data.get("correct_idx"), int)
            and 0 <= data["correct_idx"] <= 3
            and isinstance(data.get("explanation"), str)
        ):
            raise ValueError("schema invalid")
        data["card_id"] = card.id
        # usage
        data["_usage"] = {
            "input_tokens": getattr(resp.usage, "input_tokens", 0),
            "output_tokens": getattr(resp.usage, "output_tokens", 0),
        }
        return data
    except Exception:
        # Fallback — 사료 메타데이터만으로 안전한 질문 구성
        wrong_eras = ["조선 후기", "고려 중기", "신라 말기", "고구려 초기", "대한제국"]
        wrong_eras = [e for e in wrong_eras if e != card.era][:3]
        options = [card.era] + wrong_eras
        random.shuffle(options)
        return {
            "question": f"〈{card.title}〉은(는) 어느 시대의 사건입니까?",
            "options": options,
            "correct_idx": options.index(card.era),
            "explanation": f"{card.summary}\n_「출처: {card.source} [{card.id}]」_",
            "card_id": card.id,
            "_fallback": True,
        }


# ─────────────────────────────────────────────────────────────
# 테마별 사료 풀
# ─────────────────────────────────────────────────────────────
# 키: 테마 이름 (다국어 라벨은 prompts.py UI_TEXT 에서)
# 값: 매칭 키워드 (title·tags·era·place 어디든 들어가면 매칭)
QUEST_THEME_KEYWORDS: dict[str, list[str]] = {
    "all":          [],
    "palaces":      ["경복궁", "창덕궁", "창경궁", "덕수궁", "종묘", "중명전", "경기전"],
    "gyeongju":     ["경주", "신라", "통일신라", "불국사", "석굴암", "첨성대", "안압지"],
    "danyang":      ["단양"],
    "andong":       ["안동", "도산서원", "하회"],
    "imjin":        ["임진왜란", "이순신", "한산도", "진주성", "논개"],
    "joseon_kings": ["세종", "정조", "영조", "태종", "성종", "사도세자", "단종"],
    "colonial":     ["일제강점기", "독립운동", "안중근", "윤봉길", "유관순", "신채호",
                     "이회영", "광복군", "의열단", "신간회", "3.1운동", "이봉창",
                     "조선어학회", "위안부", "광주학생"],
    "historians":   ["삼국사기", "삼국유사", "고려사", "조선왕조실록", "승정원일기",
                     "일성록", "동사강목", "한국통사", "조선상고사", "사관", "사료"],
}


def _matches_theme(card: SourceCard, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = " ".join(
        [card.title, card.era, card.place, " ".join(card.tags),
         " ".join(card.related_persons), card.summary[:200]]
    ).lower()
    return any(k.lower() in haystack for k in keywords)


def pick_card(theme: str = "all", exclude_ids: list[str] | None = None) -> SourceCard:
    """테마와 일치하는 사료 중 하나를 무작위로 선택. 직전에 본 카드는 제외."""
    corpus = load_corpus()
    keywords = QUEST_THEME_KEYWORDS.get(theme, [])
    excluded = set(exclude_ids or [])
    pool = [c for c in corpus if _matches_theme(c, keywords) and c.id not in excluded]
    if not pool:
        # exclude_ids로 인해 다 떨어졌으면 무시
        pool = [c for c in corpus if _matches_theme(c, keywords)]
    if not pool:
        pool = corpus
    return random.choice(pool)


__all__ = [
    "generate_question",
    "pick_card",
    "QUEST_THEME_KEYWORDS",
]
