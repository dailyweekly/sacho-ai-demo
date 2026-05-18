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
    avoid_qtypes: list[str] | None = None,
) -> dict[str, Any]:
    """사료 카드 한 건으로 4지선다 + 해설 + 선지별 코멘트 생성.

    qtype: 명시 시 해당 유형으로 출제, None 이면 무작위.
    avoid_qtypes: 같은 카드에 직전에 나왔던 유형을 피해서 다른 각도로 출제.
    """
    client = get_client()
    lang_name = _LANG_MAP.get(language, "한국어")
    if qtype not in QUESTION_TYPES:
        avoid = set(avoid_qtypes or [])
        pool = [k for k in QUESTION_TYPES.keys() if k not in avoid]
        if not pool:
            pool = list(QUESTION_TYPES.keys())
        qtype = random.choice(pool)
    type_hint = QUESTION_TYPES[qtype]

    family_hint = (
        "응답 톤: 만 8세 이상 가족용. 어휘는 쉽게, 문장은 짧게."
        if mode and mode.startswith("가족")
        else ""
    )

    # K-콘텐츠 entry — '과거에서 미래로 떨어진 사관' 페르소나 + 진실 강조
    kculture_hint = ""
    if card.id.startswith("kculture-"):
        kculture_hint = (
            "\n[K-콘텐츠 출제 페르소나 — 시간 이동 사관]\n"
            "당신은 1905년 정동에서 갑자기 2026년으로 떨어진 졸자(拙者) 사관입니다.\n"
            "영화·드라마·애니메이션이라는 신묘한 '활동 그림자(影戱)'를 보고\n"
            "당황·감탄·기쁨이 섞인 옛 어투로 1인칭 서술하세요.\n"
            "예: '어어… 후세 사람들이 K-pop이라 부르는 노래로 우리 무녀의 굿을\n"
            "    대신하고 있더이다. 헌트릭스라 했지요…'\n"
            "그러나 페르소나는 '톤'에만 적용 — 사실은 절대 왜곡 금지.\n"
            "사료에 적힌 내용만으로 질문·정답·해설을 구성하고,\n"
            "사료에 없는 장면·대사·인물·줄거리를 임의로 만들어 내지 마십시오.\n"
            "\n"
            "[K-콘텐츠 출제 4가지 패턴 — 1개 선택]\n"
            "  1) 무대 매핑: '이 작품의 무대가 된 실제 장소/사적은?'\n"
            "  2) 역사 닻:   '이 작품이 다룬 역사 사건은 실제로 언제·어디서?'\n"
            "  3) 모티브 출처: '이 작품 속 ○○의 모티브가 된 실제 ○○는?'\n"
            "  4) 방문 가이드: '이 작품 배경지를 지금 가려면 어디로?'\n"
            "단순 작품 트리비아(주연·감독·시청률 수치)는 피하세요 — "
            "콘텐츠↔실제 한국 문화·장소·역사 연결이 핵심입니다.\n"
            "explanation에서 작품의 실제 한국 문화 배경을 짧게 풀고, "
            "방문 가능한 장소·전통을 명확히 언급하세요."
        )

    # 시드 nonce — 같은 카드·같은 유형이라도 호출마다 다른 각도로 출제하도록
    # LLM 응답에 영향은 없지만 프롬프트 동일성을 깨서 캐시·결정성 방지
    nonce = random.randint(100000, 999999)

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
        f"{family_hint}\n\n"
        f"[중요] 같은 사료라도 매번 다른 관점·인물·디테일을 골라 출제하시오. "
        f"같은 질문을 반복하지 말 것. (seed: {nonce})"
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
# 큐레이션 코스 — 도보 권역 단위 (걸을 수 있는 거리 안)
# ─────────────────────────────────────────────────────────────
COURSES: dict[str, dict[str, Any]] = {
    "jeongdong": {
        "name_ko": "🚶 정동·덕수궁 7단서 (중구, 도보 1.8km)",
        "name_en": "🚶 Jeongdong & Deoksugung — 7 clues (1.8 km walk)",
        "name_ja": "🚶 貞洞・徳寿宮 7手がかり (徒歩1.8km)",
        "name_zh": "🚶 贞洞·德寿宫 7线索 (步行1.8km)",
        "area_ko": "서울 중구 정동길 일대",
        "difficulty": 2, "est_minutes": 35, "distance_km": 1.8,
        "card_ids": [
            "sillok-009",   # 정동제일교회 (출발)
            "sillok-001",   # 아관파천 (구 러시아공사관 터)
            "sillok-002",   # 환궁 (덕수궁)
            "sillok-004",   # 대한제국 선포 (환구단, 정동 인접)
            "sillok-007",   # 을사늑약 (덕수궁 중명전)
            "place-020",    # 중명전 자체
            "sillok-010",   # 헤이그 특사 (결말)
        ],
    },
    "jongno_palaces": {
        "name_ko": "🚶 종로 4대 궁궐 산책 5단서 (도보 2km)",
        "name_en": "🚶 Jongno Palace Walk — 5 clues (2 km)",
        "name_ja": "🚶 鍾路 王宮散歩 5手がかり",
        "name_zh": "🚶 钟路宫阙漫步5线索",
        "area_ko": "서울 종로구 (경복궁~창덕궁~창경궁~종묘)",
        "difficulty": 2, "est_minutes": 30, "distance_km": 2.0,
        "card_ids": [
            "place-001",    # 경복궁
            "hist-011",     # 훈민정음 반포 (경복궁)
            "place-002",    # 창덕궁
            "place-004",    # 창경궁
            "place-003",    # 종묘
        ],
    },
    "bukchon_kpdh": {
        "name_ko": "🎬 케데헌 × 북촌 5단서 (도보 1.5km)",
        "name_en": "🎬 KPDH × Bukchon — 5 clues (1.5 km walk)",
        "name_ja": "🎬 KPDH × 北村 5手がかり",
        "name_zh": "🎬 KPDH × 北村5线索",
        "area_ko": "서울 종로구 북촌·가회동·삼청동",
        "difficulty": 1, "est_minutes": 25, "distance_km": 1.5,
        "card_ids": [
            "kculture-017",  # KPDH 배경 ↔ 북촌 한옥마을
            "kculture-015",  # KPDH 헌트릭스 ↔ 무녀 전통
            "kculture-016",  # KPDH 사자 보이즈 ↔ 저승사자
            "kculture-006",  # 케데헌 전체작 ↔ 무속·도깨비·한옥
            "place-003",     # 종묘 (북촌 인접 — 전통 정신의 거점)
        ],
    },
    "jongno_kculture": {
        "name_ko": "🎬 K-콘텐츠 ↔ 종로·중구 5장면 (도보권)",
        "name_en": "🎬 K-content × Jongno·Jung-gu — 5 scenes (walkable)",
        "name_ja": "🎬 Kコンテンツ × 鍾路 5場面",
        "name_zh": "🎬 K内容 × 钟路·中区5场景",
        "area_ko": "서울 종로·중구 (정동~창덕궁~창경궁~낙선재)",
        "difficulty": 2, "est_minutes": 25, "distance_km": 2.5,
        "card_ids": [
            "kculture-001",  # 미스터 션샤인 ↔ 손탁호텔 (정동)
            "kculture-004",  # 광해 ↔ 창덕궁
            "kculture-011",  # 슈룹 ↔ 창경궁·창덕궁
            "kculture-002",  # 사도 ↔ 창경궁
            "kculture-005",  # 덕혜옹주 ↔ 낙선재 (창덕궁 안)
        ],
    },
    "gyeongju_5": {
        "name_ko": "🚶 경주 신라 5단서 (경주 시내 권역)",
        "name_en": "🚶 Gyeongju (Silla) — 5 clues (city area)",
        "name_ja": "🚶 慶州(新羅) 5手がかり (市内)",
        "name_zh": "🚶 庆州(新罗)5线索 (市内)",
        "area_ko": "경상북도 경주 시내",
        "difficulty": 1, "est_minutes": 30, "distance_km": 3.0,
        "card_ids": [
            "place-006",    # 첨성대
            "place-007",    # 안압지(월지)
            "hist-003",     # 삼국통일
            "place-005",    # 불국사·석굴암
            "hist-004",     # 장보고 청해진 (참고)
        ],
    },
    "danyang_palgyeong": {
        "name_ko": "🚶 단양 단양팔경 2단서 (자연 명소)",
        "name_en": "🚶 Danyang Palgyeong — 2 clues",
        "name_ja": "🚶 丹陽 八景 2手がかり",
        "name_zh": "🚶 丹阳八景2线索",
        "area_ko": "충북 단양군",
        "difficulty": 1, "est_minutes": 15, "distance_km": 0.8,
        "card_ids": [
            "place-008",    # 도담삼봉
            "place-009",    # 사인암
        ],
    },
    "gbg_inside": {
        "name_ko": "🏯 경복궁 안에서 7단서 (300m 반경)",
        "name_en": "🏯 Inside Gyeongbokgung — 7 clues (300m radius)",
        "name_ja": "🏯 景福宮の内側 7手がかり",
        "name_zh": "🏯 景福宫内7线索",
        "area_ko": "경복궁 정문~건청궁 (도보 300m 반경)",
        "difficulty": 2, "est_minutes": 40, "distance_km": 0.6,
        "card_ids": [
            "gbg-001",   # 광화문 (출발)
            "gbg-002",   # 근정전
            "gbg-004",   # 사정전
            "gbg-005",   # 강녕전·교태전
            "gbg-003",   # 경회루
            "gbg-006",   # 향원정
            "gbg-007",   # 건청궁 옥호루 (을미사변 — 결말)
        ],
    },
    "dsg_inside": {
        "name_ko": "🏛 덕수궁 안에서 5단서 (250m 반경)",
        "name_en": "🏛 Inside Deoksugung — 5 clues (250m radius)",
        "name_ja": "🏛 徳寿宮の内側 5手がかり",
        "name_zh": "🏛 德寿宫内5线索",
        "area_ko": "덕수궁 대한문~함녕전 (도보 250m 반경)",
        "difficulty": 2, "est_minutes": 30, "distance_km": 0.5,
        "card_ids": [
            "dsg-001",   # 대한문 (출발)
            "dsg-002",   # 중화전
            "dsg-003",   # 석조전
            "dsg-004",   # 정관헌
            "dsg-005",   # 함녕전 (고종 승하 — 결말)
        ],
    },
    # 광화문 일대 600년 비사(秘史) — 잘 안 알려진 8가지 이야기
    # 광화문 정문 앞에서 시작해 동십자각·육조거리·세종로 동상·청계천·종로까지
    # 도보 ~1.2km 반경, 한국 600년 정치·민주화·복원사의 압축 코스
    "ghm_secrets": {
        "name_ko": "🔍 광화문 600년 비사 — 8단서 (도보 1.2km)",
        "name_en": "🔍 Gwanghwamun 600-year secrets — 8 clues (1.2km walk)",
        "name_ja": "🔍 光化門600年秘史 — 8手がかり",
        "name_zh": "🔍 光化門600年秘史 — 8线索",
        "area_ko": "광화문 정문~보신각 (도보 1.2km · 흥미진진 비사 위주)",
        "difficulty": 3, "est_minutes": 50, "distance_km": 1.2,
        "card_ids": [
            "ghm-001",   # 광화문 현판 (출발 — 글씨 6번 변천)
            "ghm-008",   # 월대 (100년 만에 돌아온 단)
            "ghm-002",   # 동십자각 (왜 길 한복판에?)
            "ghm-003",   # 육조거리 (광장 자리는 조선 6대 관청가)
            "ghm-007",   # 세종로 두 동상 (이순신 칼은 항복 자세?)
            "ghm-006",   # 광장 시위사 (4.19/6월/촛불)
            "ghm-004",   # 청계천 광통교 (거꾸로 박힌 묘석)
            "ghm-005",   # 보신각 (33번·28번의 의미 — 결말)
        ],
    },
}


def course_card_count(course_id: str) -> int:
    return len(COURSES.get(course_id, {}).get("card_ids", []))


def course_meta(course_id: str) -> dict[str, Any]:
    """코스 메타 — 난이도(★/★★/★★★), 소요시간, 거리, 단서 수.
    UI badge 렌더링 helper. 누락된 키는 합리적 기본값으로 채움."""
    c = COURSES.get(course_id, {})
    diff_n = int(c.get("difficulty", 2))
    diff_n = max(1, min(3, diff_n))
    return {
        "difficulty": diff_n,
        "difficulty_stars": "★" * diff_n + "☆" * (3 - diff_n),
        "est_minutes": int(c.get("est_minutes", 30)),
        "distance_km": float(c.get("distance_km", 1.5)),
        "card_count": len(c.get("card_ids", [])),
    }


# 난이도 라벨 — 다국어 (P1-2 badge)
DIFFICULTY_LABELS = {
    "ko": {1: "쉬움", 2: "보통", 3: "도전"},
    "en": {1: "Easy", 2: "Normal", 3: "Challenge"},
    "ja": {1: "やさしい", 2: "ふつう", 3: "挑戦"},
    "zh": {1: "简单", 2: "普通", 3: "挑战"},
}


def difficulty_label(course_id: str, lang: str = "ko") -> str:
    """난이도 텍스트 라벨 (쉬움/보통/도전)."""
    n = course_meta(course_id)["difficulty"]
    return DIFFICULTY_LABELS.get(lang, DIFFICULTY_LABELS["ko"])[n]


# ─────────────────────────────────────────────────────────────
# 다음 추천 코스 — 완주 화면 engagement loop (P1-3)
# ─────────────────────────────────────────────────────────────
# 큐레이션 narrative — 권역 zoom-in/zoom-out + 난이도 점진 상승
NEXT_COURSE_CHAIN: dict[str, str] = {
    "jeongdong":         "dsg_inside",        # 정동 → 덕수궁 안쪽 (zoom-in)
    "dsg_inside":        "ghm_secrets",       # 덕수궁 → 광화문 비사 (난이도 ↑)
    "ghm_secrets":       "gbg_inside",        # 광화문 → 경복궁 내부
    "gbg_inside":        "jongno_palaces",    # 경복궁 → 4대궁 산책
    "jongno_palaces":    "bukchon_kpdh",      # 4대궁 → 북촌 케데헌
    "bukchon_kpdh":      "jongno_kculture",   # 북촌 → 종로 K-콘텐츠
    "jongno_kculture":   "gyeongju_5",        # 서울 → 경주 (지방 확장)
    "gyeongju_5":        "danyang_palgyeong", # 경주 → 단양 자연
    "danyang_palgyeong": "jeongdong",         # 단양 → 다시 정동 (loop)
}


def next_course_for(current_id: str, tier: str = "apprentice") -> str | None:
    """완주 후 다음 추천 코스. 칭호별 살짝 분기.

    - master/companion(고득점): 큐레이션 체인 그대로 (다음 도전 자연 유도)
    - apprentice/novice(저득점): 같은/낮은 난이도 우선 — 좌절 완화
    """
    if current_id not in COURSES:
        return None
    chain_next = NEXT_COURSE_CHAIN.get(current_id)
    cur_diff = course_meta(current_id)["difficulty"]

    if tier in ("apprentice", "novice"):
        # 다음이 더 어려우면 — 같은/낮은 난이도 코스로 우회 추천
        if chain_next and course_meta(chain_next)["difficulty"] > cur_diff:
            easier = [
                cid for cid, c in COURSES.items()
                if cid != current_id
                and course_meta(cid)["difficulty"] <= cur_diff
            ]
            if easier:
                # 결정성 — 코스 키 알파벳 순으로 첫 항목
                return sorted(easier)[0]
        return chain_next
    # master/companion — 체인 그대로
    return chain_next


# 다음 코스 hook 멘트 (칭호별 살짝 톤 조절) — 다국어
NEXT_COURSE_HOOK = {
    "ko": {
        "master":     "🏆 한 코스 정복하셨소이다. 다음 도전은…",
        "companion":  "🌿 좋은 흐름이오. 이 권역도 같이 보겠소?",
        "apprentice": "📚 같이 한 권역 더 펼쳐 보겠소?",
        "novice":     "🌱 처음은 누구나 그러하오. 가볍게 한 권역만 더?",
    },
    "en": {
        "master":     "🏆 You've conquered one. Next challenge…",
        "companion":  "🌿 Nice rhythm. Care to explore this area too?",
        "apprentice": "📚 Shall we open one more area together?",
        "novice":     "🌱 Beginnings are tough. One more, lighter walk?",
    },
    "ja": {
        "master":     "🏆 一コース制覇。次の挑戦は…",
        "companion":  "🌿 よい流れ。次の地域もご一緒に。",
        "apprentice": "📚 もう一つ、開いてみますか?",
        "novice":     "🌱 最初は皆そう。気軽にもう一つ。",
    },
    "zh": {
        "master":     "🏆 已征服一程。下一挑战…",
        "companion":  "🌿 节奏正好。再走一地域吗?",
        "apprentice": "📚 再开一处吗?",
        "novice":     "🌱 初学皆如此,再走一段轻松的路?",
    },
}


def next_course_hook(tier: str, lang: str = "ko") -> str:
    """추천 hook 멘트 — 칭호 + 언어별."""
    return NEXT_COURSE_HOOK.get(
        lang, NEXT_COURSE_HOOK["ko"]
    ).get(tier, NEXT_COURSE_HOOK["ko"]["apprentice"])


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


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 사이 거리 (km)."""
    from math import radians, sin, cos, asin, sqrt
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _is_abstract_location(card: SourceCard) -> bool:
    """위치가 모호한 entry (전국/추상 K-콘텐츠) 판별."""
    if not card.place:
        return True
    if card.id.startswith("kculture-"):
        if any(s in card.place for s in ["한국 무속", "전통 사후세계", "(전국"]):
            return True
    return False


def pick_nearest_card(
    lat: float, lon: float,
    max_km: float = 30.0,
    exclude_ids: list[str] | None = None,
) -> tuple[SourceCard | None, float]:
    """현재 위치에서 가장 가까운 사료 카드 + 거리(km). 단일 픽."""
    excluded = set(exclude_ids or [])
    best: SourceCard | None = None
    best_dist = float("inf")
    for c in load_corpus():
        if c.id in excluded or _is_abstract_location(c):
            continue
        if not c.place_coords or len(c.place_coords) != 2:
            continue
        d = _haversine_km(lat, lon, c.place_coords[1], c.place_coords[0])
        if d < best_dist:
            best_dist = d
            best = c
    if best_dist > max_km:
        return None, best_dist
    return best, best_dist


def pick_nearby_cards(
    lat: float, lon: float,
    max_km: float = 2.0,
    exclude_ids: list[str] | None = None,
    limit: int = 20,
) -> list[tuple[SourceCard, float]]:
    """현 위치에서 max_km 이내의 사료를 거리순 정렬해 반환 (limit개).

    같은 자리에서 다양한 카드를 노출할 수 있도록 '근처 다수'를 반환.
    """
    excluded = set(exclude_ids or [])
    cands: list[tuple[SourceCard, float]] = []
    for c in load_corpus():
        if c.id in excluded or _is_abstract_location(c):
            continue
        if not c.place_coords or len(c.place_coords) != 2:
            continue
        d = _haversine_km(lat, lon, c.place_coords[1], c.place_coords[0])
        if d <= max_km:
            cands.append((c, d))
    cands.sort(key=lambda x: x[1])
    return cands[:limit]


def pick_random_nearby(
    lat: float, lon: float,
    max_km: float = 2.0,
    exclude_ids: list[str] | None = None,
) -> SourceCard | None:
    """근처 사료 중 거리 가중 무작위 선택.

    같은 GPS 위치에서 매번 다른 사료가 뽑힐 수 있도록 가중 무작위.
    가중치 = 1 / (거리_km + 0.05) → 가까울수록 뽑힐 확률 ↑.
    같은 자리 같은 카드 반복 회피용 exclude_ids 인자를 함께 사용 권장.
    """
    cards = pick_nearby_cards(lat, lon, max_km, exclude_ids, limit=20)
    if not cards:
        return None
    weights = [1.0 / (d + 0.05) for _, d in cards]
    return random.choices([c for c, _ in cards], weights=weights, k=1)[0]


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
    "course_meta", "difficulty_label", "DIFFICULTY_LABELS",
    "next_course_for", "next_course_hook", "NEXT_COURSE_CHAIN",
    "QUESTION_TYPES",
    "pick_nearest_card", "pick_nearby_cards", "pick_random_nearby",
]
