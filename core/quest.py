"""한국사 객관식 퀘스트 엔진.

- generate_question(card, language, mode, qtype): 사료 카드 1건 -> 4지선다 + 해설 + 선지별 코멘트
- pick_card(theme, exclude_ids): 테마별 무작위 사료 픽
- COURSES: 순차 진행되는 큐레이션 코스 (정동·경주 등)
- pick_course_card(course_id, idx): 코스의 N번째 사료
"""
from __future__ import annotations

import json
import random
from typing import Any

from core.llm import get_client, DEFAULT_MODEL
from core.rag import SourceCard, load_corpus


# ─────────────────────────────────────────────────────────────
# 문제 유형 — 단순 암기형 회피, 추리·맥락·비교 중심
# ─────────────────────────────────────────────────────────────
QUESTION_TYPES = {
    "source_inference": (
        "유형: 사료 추론형. 사료의 명시 사실에서 한 단계 추론하는 질문 "
        "(예: '이 사건이 의미하는 바는 무엇입니까?', '왜 ~한 결과가 나왔는가?')."
    ),
    "character_motivation": (
        "유형: 인물 동기형. 사건 속 핵심 인물의 동기·선택·고민을 사료 범위 내에서 묻는 질문 "
        "(예: '~는 왜 이 결정을 내렸을까요?')."
    ),
    "place_significance": (
        "유형: 장소 의의형. 사건이 일어난 장소·유물의 역사적 의의·맥락을 묻는 질문 "
        "(예: '이 자리는 왜 중요한가요?', '이 장소가 가진 상징은?')."
    ),
    "wrong_compare": (
        "유형: 오답 비교형. 정답·오답이 모두 같은 시대 또는 비슷한 사건이라 헷갈리기 쉬운 비교 학습형. "
        "option_notes 에서 각 오답이 왜 그럴듯한데 틀렸는지 1줄로 짧게 풀어 주십시오."
    ),
    "consequence": (
        "유형: 결과·영향형. 이 사건이 이후 한국사에 어떤 결과·영향을 가져왔는지를 묻는 질문 "
        "(예: '이 사건 직후 어떤 일이 이어졌는가?')."
    ),
}


QUEST_SYSTEM = """당신은 한국사 객관식 출제관입니다.
주어진 사료 1건만을 근거로 객관식 문제 1개를 JSON 형식으로 만드십시오.

# 출제 원칙 (절대 준수)
1. 질문·정답은 **사료에 명시된 사실**(인물·연·월·일·장소·사건·관련 인물)에서만 도출.
2. 단순 연도 암기 회피 — 추리·맥락·비교 중심으로 설계.
3. 선지 4개:
   - 1개 정답 (사료에 명시)
   - 3개 오답 (같은 시대/비슷한 사건/인접 장소 등 헷갈리기 쉬운 그럴듯한 항목)
4. correct_idx: 정답 위치 (0~3에 무작위 배치)
5. explanation: 5~8문장 상세 해설.
   - 어려운 한자어는 괄호 풀이
   - 본문 안에 사료 id를 [card_id] 형식으로 1~2번 인라인 마커
   - 끝에 _「출처: 〈사료 제목〉 [card_id]」_
6. **option_notes**: 4개 선지 각각에 대한 1~2줄 코멘트
   - 정답 선지: "정답. 사료에 따르면 …"
   - 오답 선지: "그럴듯하지만, 실제로는 …" (왜 헷갈리는데 틀렸는지)
7. 학설이 갈리는 사안은 explanation 에 양측 견해 짧게 병기.

# 출력 형식
다음 JSON만 출력 (다른 텍스트·코드펜스 절대 금지):
{
  "question": "질문 문장",
  "options": ["선지A", "선지B", "선지C", "선지D"],
  "correct_idx": 0,
  "option_notes": ["A 코멘트", "B 코멘트", "C 코멘트", "D 코멘트"],
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
    qtype: str | None = None,
) -> dict[str, Any]:
    """사료 카드 한 건으로 4지선다 + 해설 + 선지별 코멘트 생성.

    qtype: 명시 시 해당 유형으로 출제, None 이면 무작위.
    """
    client = get_client()
    lang_name = _LANG_MAP.get(language, "한국어")
    if qtype not in QUESTION_TYPES:
        qtype = random.choice(list(QUESTION_TYPES.keys()))
    type_hint = QUESTION_TYPES[qtype]

    family_hint = (
        "응답 톤: 만 8세 이상 가족용. 어휘는 쉽게, 문장은 짧게."
        if mode and mode.startswith("가족")
        else ""
    )

    # K-콘텐츠 entry는 작품 ↔ 실제 장소/사건 연결 질문을 우선
    kculture_hint = ""
    if card.id.startswith("kculture-"):
        kculture_hint = (
            "\n[K-콘텐츠 출제 가이드 — 이 entry는 영화/드라마/애니메이션이 "
            "실제 한국 사적·장소·역사 사건과 연결되는 카드입니다]\n"
            "다음 4가지 패턴 중 1개를 골라 질문하십시오:\n"
            "  1) 무대 매핑: '이 작품의 무대가 된 실제 장소/사적은?'\n"
            "  2) 역사 닻: '이 작품이 다룬 역사 사건은 실제로 언제·어디서?'\n"
            "  3) 모티브 출처: '이 작품 속 ○○의 모티브가 된 실제 ○○는?'\n"
            "  4) 방문 가이드: '이 작품 촬영지/배경지를 지금 가려면 어디로?'\n"
            "단순 작품 트리비아(주연·감독·시청률)는 피하세요 — "
            "콘텐츠↔실제 연결이 핵심입니다.\n"
            "explanation에서 작품의 실제 역사 배경을 짧게 풀고, "
            "방문 가능한 장소를 명확히 언급하세요."
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
        f"[문제 유형]\n{type_hint}\n"
        f"{kculture_hint}\n"
        f"[응답 언어] {lang_name}로 작성. 단, 사료 id 마커는 [{card.id}] 그대로.\n"
        f"{family_hint}"
    )

    try:
        resp = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1500,
            temperature=0.45,
            system=QUEST_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text.strip()
        # 코드펜스 안전 제거
        if text.startswith("```"):
            for chunk in text.split("```"):
                chunk = chunk.strip()
                if chunk.startswith("json"):
                    chunk = chunk[4:].strip()
                if chunk.startswith("{"):
                    text = chunk
                    break

        data = json.loads(text)
        opts = data.get("options", [])
        notes = data.get("option_notes", [""] * 4)
        if len(notes) < 4:
            notes = (notes + [""] * 4)[:4]
        if not (
            isinstance(data.get("question"), str)
            and isinstance(opts, list) and len(opts) == 4
            and isinstance(data.get("correct_idx"), int)
            and 0 <= data["correct_idx"] <= 3
            and isinstance(data.get("explanation"), str)
        ):
            raise ValueError("schema invalid")

        data["option_notes"] = notes
        data["card_id"] = card.id
        data["qtype"] = qtype
        data["_usage"] = {
            "input_tokens": getattr(resp.usage, "input_tokens", 0),
            "output_tokens": getattr(resp.usage, "output_tokens", 0),
        }
        return data
    except Exception:
        # Fallback: 사료 메타로만 안전하게
        wrong_eras = ["조선 후기", "고려 중기", "신라 말기", "고구려 초기", "대한제국"]
        wrong_eras = [e for e in wrong_eras if e != card.era][:3]
        options = [card.era or "조선"] + wrong_eras
        random.shuffle(options)
        return {
            "question": f"〈{card.title}〉은(는) 어느 시대의 사건입니까?",
            "options": options,
            "correct_idx": options.index(card.era or "조선"),
            "option_notes": [
                f"이 사건은 {card.era}에 일어났습니다." if o == card.era else f"이 사건은 {o}이 아니라 {card.era}에 속합니다."
                for o in options
            ],
            "explanation": f"{card.summary}\n_「출처: {card.source} [{card.id}]」_",
            "card_id": card.id,
            "qtype": "fallback",
            "_fallback": True,
        }


# ─────────────────────────────────────────────────────────────
# 테마 (무작위 풀)
# ─────────────────────────────────────────────────────────────
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
    "kculture":     ["미스터션샤인", "사도", "광해", "명량", "덕혜옹주", "오징어게임",
                     "케데헌", "KPopDemonHunters", "Netflix", "K드라마", "K영화",
                     "K애니메이션", "콘텐츠투어리즘", "촬영지"],
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
    corpus = load_corpus()
    keywords = QUEST_THEME_KEYWORDS.get(theme, [])
    excluded = set(exclude_ids or [])
    pool = [c for c in corpus if _matches_theme(c, keywords) and c.id not in excluded]
    if not pool:
        pool = [c for c in corpus if _matches_theme(c, keywords)]
    if not pool:
        pool = corpus
    return random.choice(pool)


# ─────────────────────────────────────────────────────────────
# 큐레이션 코스 — 순차 진행 + 엔딩
# ─────────────────────────────────────────────────────────────
COURSES: dict[str, dict[str, Any]] = {
    "jeongdong": {
        "name_ko": "정동·덕수궁 7단서 (MVP 코스)",
        "name_en": "Jeongdong & Deoksugung — 7 clues",
        "name_ja": "貞洞・徳寿宮 7手がかり",
        "name_zh": "贞洞·德寿宫 7线索",
        "card_ids": [
            "sillok-009",   # 1. 정동제일교회 (출발)
            "sillok-001",   # 2. 아관파천 (구 러시아공사관 터)
            "sillok-002",   # 3. 환궁 (덕수궁)
            "sillok-004",   # 4. 대한제국 선포 (환구단)
            "sillok-007",   # 5. 을사늑약 (덕수궁 중명전)
            "place-020",    # 6. 중명전 자체
            "sillok-010",   # 7. 헤이그 특사 (결말)
        ],
    },
    "gyeongju_5": {
        "name_ko": "경주 신라 5단서",
        "name_en": "Gyeongju (Silla) — 5 clues",
        "name_ja": "慶州(新羅) 5手がかり",
        "name_zh": "庆州(新罗)5线索",
        "card_ids": [
            "place-006",    # 첨성대
            "hist-003",     # 삼국통일
            "place-007",    # 안압지
            "place-005",    # 불국사·석굴암
            "hist-004",     # 장보고 청해진
        ],
    },
    "joseon_open": {
        "name_ko": "조선의 시작 5단서",
        "name_en": "Joseon Origins — 5 clues",
        "name_ja": "朝鮮のはじまり 5手がかり",
        "name_zh": "朝鲜的起点 5线索",
        "card_ids": [
            "hist-009",     # 위화도 회군
            "hist-008",     # 정몽주 선죽교
            "hist-010",     # 조선 건국
            "place-001",    # 경복궁 창건
            "place-003",    # 종묘
        ],
    },
    "kculture_seoul": {
        "name_ko": "🎬 K-콘텐츠 ↔ 서울 7장면",
        "name_en": "🎬 K-content × Seoul — 7 scenes",
        "name_ja": "🎬 Kコンテンツ × ソウル 7場面",
        "name_zh": "🎬 K内容 × 首尔7场景",
        "card_ids": [
            "kculture-001",  # 미스터 션샤인 ↔ 손탁호텔 (정동)
            "kculture-004",  # 광해 ↔ 창덕궁
            "kculture-002",  # 사도 ↔ 창경궁
            "kculture-011",  # 슈룹 ↔ 창경궁/창덕궁
            "kculture-005",  # 덕혜옹주 ↔ 낙선재
            "kculture-009",  # 응답하라 1988 ↔ 쌍문동
            "kculture-007",  # 오징어 게임 ↔ 옥수동
        ],
    },
    "kculture_period": {
        "name_ko": "🎬 시대극으로 보는 한국사 5장면",
        "name_en": "🎬 Korean history through period dramas",
        "name_ja": "🎬 時代劇で見る韓国史 5場面",
        "name_zh": "🎬 透过时代剧看韩国史",
        "card_ids": [
            "kculture-010",  # 한산 (1592 임진왜란)
            "kculture-004",  # 광해 (1616)
            "kculture-002",  # 사도 (1762)
            "kculture-001",  # 미스터 션샤인 (1885~1907)
            "kculture-005",  # 덕혜옹주 (1962 환국)
        ],
    },
}


def course_card_count(course_id: str) -> int:
    return len(COURSES.get(course_id, {}).get("card_ids", []))


def pick_course_card(course_id: str, idx: int) -> SourceCard | None:
    """코스 N번째 사료 카드 반환. 범위 밖이면 None."""
    course = COURSES.get(course_id)
    if not course:
        return None
    ids = course["card_ids"]
    if idx < 0 or idx >= len(ids):
        return None
    target_id = ids[idx]
    for c in load_corpus():
        if c.id == target_id:
            return c
    return None


def ending_tier(score: int, total: int) -> str:
    """정답률에 따른 엔딩 티어 키."""
    if total <= 0:
        return "novice"
    ratio = score / total
    if ratio >= 0.95:
        return "master"      # 사관의 으뜸
    if ratio >= 0.7:
        return "companion"   # 사관의 동무
    if ratio >= 0.4:
        return "apprentice"  # 사관의 견습
    return "novice"          # 다음에 또 오시구려


__all__ = [
    "generate_question", "pick_card", "QUEST_THEME_KEYWORDS",
    "COURSES", "course_card_count", "pick_course_card", "ending_tier",
    "QUESTION_TYPES",
]
