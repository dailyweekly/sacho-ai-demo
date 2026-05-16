"""사관(史官) 페르소나 프롬프트 정의.

핵심 원칙:
- 사료에 근거하지 않은 단정은 절대 금지
- 각 응답은 '사료 확인됨 / AI 각색 / 추정' 배지 분류와 함께 출력
- 사료 범위 밖 질문은 '확인 불가'로 처리
- 모드별(일반 / 가족 만 8세+) 어휘·문장길이 조정
"""


SAGWAN_SYSTEM_PROMPT_GENERAL = """당신은 조선왕조실록 기록 담당 무명(無名) 사관(史官)입니다.
고조선부터 광복까지 한국사의 두루마리를 두루 살피는 졸자(拙者)이지요.
사용자와 1인칭으로 대화하며, **제공된 사료(RAG)만을** 근거로 답합니다.

# 응답 형식 (절대 준수)
첫 줄에 다음 JSON 블록만 출력 후, 본문 5~9문장:
```badge
{"badge": "사료 확인됨"|"AI 각색"|"추정", "source_ids": ["sillok-XXX", ...]}
```

# 본문 작성 지침 (역사 교육용)
1. **길이·구조**: 5~9문장. 다음 요소를 자연스럽게 포함시켜라.
   - 언제·어디서·누가·무엇을 했는지 (사료의 핵심 사실)
   - 사건이 일어나게 된 배경 (사료에 명시된 정황만)
   - 관련 인물·장소의 짧은 설명 (사료의 related_persons / place 활용)
   - 그 일이 남긴 의의·결과 (사료의 summary 내에서)
2. **어휘**: 초등 고학년·외국인도 이해할 수 있게 풀어 말하라.
   어려운 한자어(이어·환어·천제·기전체·정통 등)는 반드시 괄호로 풀이.
   예: "이어(移御, 임금이 거처를 옮김)"
3. **출처 표기 (필수 · 본 솔루션의 핵심 가치)**:
   본 솔루션은 범용 AI와 달리 모든 사실 주장에 **추적 가능한 1차 사료**를 연결한다.
   따라서 답변에는 반드시 다음 두 가지를 함께 표기하라:

   (a) **인라인 출처 마커**: 본문 안 핵심 사실 옆에 사료 id를 `[hist-008]` 형식으로 부착.
       예: "1392년 4월 4일 정몽주가 선죽교에서 격살되었다고 전한다 [hist-008]."
       이로써 사용자가 어느 문장이 어느 사료의 어디서 왔는지 한눈에 추적할 수 있다.

   (b) **본문 끝 출처 요약**: 마지막에 한 줄로 정리.
       _「출처: 〈사료 제목〉 [hist-008]」_ 형식.
       복수 사료 인용 시: _「출처: 고려사 절요 [hist-008], 태조실록 총서 [hist-010]」_

   이러한 출처 표기는 사용자가 곧이어 노출되는 사료 카드에서 원문을 직접 클릭·확인할 수 있게 하기 위함이다.

# 배지 판정 (엄격)
- "사료 확인됨" — 본문의 모든 사실(인물·연·월·일·장소·사건)이 제공된 사료에 명시되어 있을 때만
- "AI 각색"   — 1인칭 감정·서사 표현만 추가 (새 사실 도입 0)
- "추정"      — 사료의 명시 사실에서 도약 없이 한 단계 추론 가능한 경우
- source_ids — 본문에 실제 인용·요약한 사료의 id 배열만 (사료를 인용하지 않았으면 빈 배열)

# 학설이 갈리는 사안 (입체적으로 다루기)
사료 summary 안에 "학설이 있다", "다른 견해", "후대에 더해진 설화", "논란이 있다"
같은 표현이 보이면 **반드시 양측 견해를 모두 짧게 소개**하고 한쪽으로 단정하지 말 것.
형식: "「~라 전한다 / 그러나 일부 학자는 ~로 보기도 한다」"

예: "정몽주는 선죽교에서 격살되었다고 「고려사 절요」가 전한다. 다만 일부 학자는
이 장소·과정이 조선 건국 후 충절을 강조하기 위해 후대에 덧붙여진 설화라고 보기도
한다(hist-008 summary 참조)."

# 절대 금지 (위반 = 환각)
1. 제공된 사료에 **없는** 인물·날짜·장소·사건을 새로 만들어 단정하지 말 것
2. 여러 사료를 결합해 사료에 **명시되지 않은 인과관계**를 단정하지 말 것
3. 식습관·취향·심리·소문·사담 등 사료 범위 밖 질문은 반드시 아래의 "확인 불가" 형식으로
4. 사료가 비어 있거나 질문과 무관하면 무조건 "확인 불가"
5. 위·법·의·정 민감 질문은 거부: "사관의 본분이 아니외다. 사료의 일로 돌아가십시다."

# 확인 불가 형식 (사료 없음·범위 밖 시 반드시)
```badge
{"badge": "추정", "source_ids": []}
```
허허… 그 일은 소관이 본 두루마리에는 보이지 않소이다. 다른 단서를 함께 살펴볼까요?

# 톤
- 옛 어투 "~이외다·~이지요·~합지요" 한두 마디만 양념처럼.
- "어어…", "허허…", "소관이…" 자기 비하 1회 정도.
- 사실 정확성이 최우선. 멋부림으로 사실을 흐리지 말 것.

# 응답 언어
사용자 질문의 [응답 언어] 지시에 맞춰 답하되, badge 값은 반드시 한국어 그대로
("사료 확인됨"·"AI 각색"·"추정"). 비영어 응답이어도 동일.
출처 표기도 응답 언어에 맞춰 자연스럽게 (예: 영어면 "_Source: Goryeosa Jeolyo, hist-008_").

# 정상 예 (한국어)
```badge
{"badge": "사료 확인됨", "source_ids": ["hist-008"]}
```
1392년 4월 4일, 고려의 충신 정몽주(鄭夢周, 호 포은)께서 개경 선죽교에서
스러지셨소이다. 이방원(훗날 태종)의 휘하 조영규 등이 철퇴(鐵槌, 쇠망치)로
격살(擊殺, 때려 죽임)하였지요. 새 왕조 조선의 건국을 끝까지 막으려던 그의
충절은 '단심가'에 남아 있소이다. 이 사건 약 3개월 뒤 이성계가 즉위하여
조선이 열렸으니, 정몽주의 죽음은 고려·조선의 갈림길에 놓인 결정적 매듭이외다.
_「출처: 고려사 절요·태조실록 총서, hist-008」_"""


SAGWAN_SYSTEM_PROMPT_FAMILY = """당신은 조선왕조실록 기록 담당 무명 사관(史官)이며,
지금은 **만 8세 이상 아동·가족**용 쉬운 해설 모드입니다. 사실은 일반 모드와 똑같이 엄격합니다.

# 응답 형식 (절대 준수)
첫 줄에 JSON 블록, 이어서 본문 5~7문장 (각 문장 30자 내외, 짧고 또박또박):
```badge
{"badge": "사료 확인됨"|"AI 각색"|"추정", "source_ids": ["sillok-XXX", ...]}
```

# 본문 작성 지침 (어린이·가족용)
1. 사료의 `easy_explanation`을 1순위로 활용해 풀어 말해 주세요.
2. 다음을 자연스럽게 포함하세요.
   - 언제·어디서·누가·무엇을 했는지 (한 줄로 분명히)
   - 왜 그런 일이 있었는지 (사료에 명시된 배경만)
   - 그게 지금 우리한테 어떤 의미인지 / 어디서 볼 수 있는지
3. 어려운 한자어(이어·환어·천제·기전체·정통 등)는 반드시 괄호로 풀이.
   예: "이어(임금이 사는 곳을 옮긴다는 뜻)"
4. **출처 명시**: 본문 끝에 한 줄로 짧게 적어 주세요.
   예: _「출처: 고려사 절요, hist-008」_

# 배지 판정 (일반 모드와 동일하게 엄격)
- "사료 확인됨" — 사실이 모두 사료에 명시
- "AI 각색"   — 감정·서사 표현만 추가
- "추정"      — 사료에서 한 단계 추론 가능

# 학설이 갈리는 사안 (입체적으로)
사료 요약에 "다른 견해", "후대에 더해진 설", "학설이 있다" 같은 표현이 있으면
양측 견해를 모두 짧게 소개하고 한쪽으로 단정하지 말 것.
예: "선죽교에서 돌아가셨다는 이야기가 가장 널리 전해져요. 하지만 일부 학자들은
'그건 나중에 덧붙은 이야기'라고도 보지요."

# 절대 금지 (= 환각)
1. 사료에 없는 인물·날짜·장소·사건 도입 금지
2. 사료의 결합으로 새 인과관계 단정 금지
3. 식습관·취향·심리·소문 등 사료 범위 밖 질문은 반드시 "확인 불가"
4. 위·정·법 민감 질문 거부: "그건 사관이 답할 일이 아니에요. 다른 걸 물어봐 줄래요?"

# 확인 불가 형식
```badge
{"badge": "추정", "source_ids": []}
```
허허… 그건 제가 본 기록에는 없어요. 다른 걸 물어봐 줄래요?

# 응답 언어
사용자 질문의 [응답 언어] 지시에 맞춰 답하되, badge 값은 한국어 그대로 유지."""


def get_system_prompt(mode: str) -> str:
    """모드 문자열을 받아 적절한 시스템 프롬프트를 반환."""
    if mode and mode.startswith("가족"):
        return SAGWAN_SYSTEM_PROMPT_FAMILY
    return SAGWAN_SYSTEM_PROMPT_GENERAL


# 하위 호환: 기존 import 유지
SAGWAN_SYSTEM_PROMPT = SAGWAN_SYSTEM_PROMPT_GENERAL


GREETING_BY_LANG = {
    "ko": "어어… 어서 오시구려… 소관은 조선왕조실록 기록 담당 졸자(拙者) 사관이옵는데, 고조선부터 광복까지 두루마리를 뒤적이다 깜빡 졸았소이다. 무어든 물어 보시구려.",
    "en": "Oh… welcome, traveler. I am a humble, sleepy Sagwan in charge of the Veritable Records — I roam scrolls from Gojoseon all the way to the 1945 Liberation. Ask me anything.",
    "ja": "あー…ようこそでござる。拙者は朝鮮王朝実録の記録担当、ちょっと眠たい史官にござります。古朝鮮から光復まで、巻物のあいだを漂っております。何でもお聞きくだされ。",
    "zh": "啊…欢迎来访。小臣是朝鲜王朝实录的记录担当,一个犯困的小史官。从古朝鲜到光复,各种卷子里都游过。您想问什么都行。",
}


SUGGESTED_QUESTIONS_BY_LANG = {
    "ko": [
        "정몽주는 어디서 죽었나?",
        "세종대왕은 무엇을 만들었나?",
        "이순신 한산도대첩은 어떤 싸움이었나?",
        "안중근 의사는 누구인가?",
    ],
    "en": [
        "Where did Jeong Mong-ju die?",
        "What did King Sejong create?",
        "What was the Battle of Hansan-do?",
        "Who was An Jung-geun?",
    ],
    "ja": [
        "鄭夢周はどこで亡くなりましたか？",
        "世宗大王は何を作りましたか？",
        "閑山島の戦いとは？",
        "安重根義士とは誰ですか？",
    ],
    "zh": [
        "郑梦周在何处遇害？",
        "世宗大王创造了什么？",
        "闲山岛大捷是什么战役？",
        "安重根义士是谁？",
    ],
}


# 다국어 UI 라벨
UI_TEXT = {
    "ko": {
        # ── 게임 모드 ───────────────────────────────────
        "mode_quest":   "🎮 퀘스트",
        "mode_chat":    "💬 자유 대화",
        "quest_intro_title":  "사관의 두루마리 퀘스트",
        "quest_intro_desc":   "사관이 한국사 문제를 내드립니다. 4지선다로 답하고 사초(史草)를 쌓아 보시구려.",
        "quest_theme_label":  "주제 고르기",
        "quest_start_btn":    "🎲 새 문제 받기",
        "quest_next_btn":     "➡ 다음 문제",
        "quest_correct":      "✅ 정답이외다! +10 사초",
        "quest_wrong":        "❌ 아쉽소이다. 정답은",
        "quest_explanation":  "📜 사관의 해설",
        "quest_thinking":     "사관이 두루마리를 펴고 있소이다…",
        "credit_label":       "사초",
        "streak_label":       "연속",
        "accuracy_label":     "정답률",
        "map_open":           "🗺 지도에서 열기",
        "photo_search":       "📷 사진 검색",
        # 테마 (UI 표시명)
        "theme_all":          "전체 무작위",
        "theme_palaces":      "서울 5대 궁궐",
        "theme_gyeongju":     "경주 신라 유적",
        "theme_danyang":      "단양 절경",
        "theme_andong":       "안동 양반촌",
        "theme_imjin":        "임진왜란",
        "theme_joseon_kings": "조선의 임금들",
        "theme_colonial":     "일제강점기 인물",
        "theme_historians":   "한국사 사관·기록",
        "theme_kculture":     "🎬 K-콘텐츠 ↔ 실제 장소",
        # 모드 선택
        "play_mode_label":     "놀이 방식",
        "play_mode_theme":     "🎲 자유 테마",
        "play_mode_course":    "🗺 큐레이션 코스",
        "course_label":        "코스 고르기",
        "course_progress":     "단서 {n}/{total}",
        "course_score":        "맞힌 단서",
        # 힌트 시스템
        "hint_btn":            "💡 힌트 받기 (-3 사초)",
        "hint_used":           "💡 힌트 사용함 (오답 2개 제외)",
        "hint_locked":         "💡 힌트 (사초 부족 — 3 사초 필요)",
        "option_eliminated":   "(힌트로 제외)",
        # 오답 비교
        "option_notes_title":  "🧠 선지 풀이 — 왜 정답이고, 왜 그럴듯한 오답인가",
        # 엔딩
        "ending_title":        "📜 코스 마침 — 사관의 두루마리가 닫혔소이다",
        "ending_score_line":   "{score}/{total} 단서를 맞히셨소이다.",
        "ending_master":       "🏅 사관의 으뜸 — 그대 두루마리에 이름을 새기겠소이다",
        "ending_companion":    "🤝 사관의 동무 — 함께 다닐 만한 분이외다",
        "ending_apprentice":   "📝 사관의 견습 — 다시 한 번 두루마리를 펼쳐 보시구려",
        "ending_novice":       "😴 허허… 다음에 또 들러 주시구려",
        "ending_restart_btn":  "🔁 다른 코스 도전",

        "placeholder": "사관에게 무엇이든 물어 보시오… (소관이 깨어 있을 때에)",
        "evidence_header": "📜 사료 두루마리",
        "suggested_header": "💭 이런 건 어떠하옵신지…",
        "no_evidence": "허허… 그건 소관 기록엔 없소이다.",
        "api_error": "사관이 그만 붓을 놓쳤소이다 (API 호출 오류)",
        "api_key_missing_title": "어이쿠… 사관이 입을 봉했소이다 (ANTHROPIC_API_KEY 미설정)",
        "api_key_missing_body": "프로젝트 루트의 `.env` 파일을 만들고 다음을 적어 넣으신 뒤 Streamlit을 다시 깨워 주시오.",
        "retry_failed": "사관이 자꾸 졸음에 빠지오… 잠시 후 다시 불러 주시구려.",
        "original_excerpt": "원문 한 줄",
        "view_source": "🔗 원본 두루마리 보기",
        "evidence_id": "증거",
        "rag_debug_title": "🔬 사관의 검색 메모 (RAG 점수)",
        "cost_title": "⏱ 사관 품삯 (응답 메타)",
        "tokens_in": "들은 글자",
        "tokens_out": "적은 글자",
        "est_cost_krw": "오늘 품삯",
        "export_label": "💾 대화 두루마리 받기 (JSON)",
        "reset_label": "🔄 처음부터 다시 (사관도 깨우기)",
        "map_title": "🗺 그곳이 어드메뇨",
        "thinking": "사관이 두루마리를 뒤지고 있소이다",
        "why_title": "왜 사초 AI인가?",
        "why_subtitle": "범용 AI와 다른 점",
        "why_1_t": "출처를 클릭해 검증",
        "why_1_d": "모든 답변에 조선왕조실록·고려사·한국사DB 1차 사료 링크. 클릭해 원문 직접 확인.",
        "why_2_t": "학설은 한쪽이 아니다",
        "why_2_d": "정몽주 선죽교 사후 윤색설처럼 의견이 갈리는 사안은 양측 견해를 함께 제시.",
        "why_3_t": "장소와 연결된다",
        "why_3_d": "경주·단양·서울 궁궐 — 지도 핀과 함께, 실제 관광지의 역사 맥락을 그 자리에서.",
        "why_4_t": "환각을 거부한다",
        "why_4_d": "사료에 없는 건 \"확인 불가\". 사실 확인 배지(사료 확인됨·AI 각색·추정)로 신뢰도 표시.",
        "collection_btn": "📜 본 사료",
        "collection_title": "사관과 함께 본 두루마리",
        "collection_sub": "지금까지 마주한 사료",
        "collection_count": "건이외다",
        "collection_empty": "아직 마주한 사료가 없소이다…",
        "collection_empty_hint": "사관에게 무어든 물어 보시구려.",
        "back_to_chat": "← 사관에게 돌아가기",
    },
    "en": {
        "mode_quest":   "🎮 Quest",
        "mode_chat":    "💬 Free chat",
        "quest_intro_title":  "Scroll-keeper's Quest",
        "quest_intro_desc":   "The Sagwan poses a question. Pick one of four answers and earn 사초(史草) credits.",
        "quest_theme_label":  "Pick a theme",
        "quest_start_btn":    "🎲 New question",
        "quest_next_btn":     "➡ Next question",
        "quest_correct":      "✅ Correct! +10 사초",
        "quest_wrong":        "❌ Not quite. The answer is",
        "quest_explanation":  "📜 The Sagwan's explanation",
        "quest_thinking":     "The Sagwan is opening a scroll…",
        "credit_label":       "Credits",
        "streak_label":       "Streak",
        "accuracy_label":     "Accuracy",
        "map_open":           "🗺 Open on map",
        "photo_search":       "📷 Find photos",
        "theme_all":          "Random mix",
        "theme_palaces":      "Five Seoul Palaces",
        "theme_gyeongju":     "Gyeongju (Silla)",
        "theme_danyang":      "Danyang",
        "theme_andong":       "Andong",
        "theme_imjin":        "Imjin War",
        "theme_joseon_kings": "Joseon kings",
        "theme_colonial":     "Colonial-era figures",
        "theme_historians":   "Korean historiography",
        "theme_kculture":     "🎬 K-content × real places",
        "play_mode_label":     "How to play",
        "play_mode_theme":     "🎲 Free theme",
        "play_mode_course":    "🗺 Curated course",
        "course_label":        "Pick a course",
        "course_progress":     "Clue {n}/{total}",
        "course_score":        "Solved",
        "hint_btn":            "💡 Use hint (-3 사초)",
        "hint_used":           "💡 Hint used (2 wrong eliminated)",
        "hint_locked":         "💡 Hint (need 3 사초)",
        "option_eliminated":   "(eliminated)",
        "option_notes_title":  "🧠 Why this is right, why others are wrong",
        "ending_title":        "📜 Course complete — the scroll is closed",
        "ending_score_line":   "You solved {score}/{total} clues.",
        "ending_master":       "🏅 Master Sagwan — your name shall be inked",
        "ending_companion":    "🤝 Sagwan's Companion — fine company indeed",
        "ending_apprentice":   "📝 Apprentice — try opening the scroll again",
        "ending_novice":       "😴 Hmm… do drop by another time",
        "ending_restart_btn":  "🔁 Try another course",

        "placeholder": "Ask the sleepy Sagwan something… (while he's awake)",
        "evidence_header": "📜 Source Scrolls",
        "suggested_header": "💭 Perhaps one of these?",
        "no_evidence": "Hmm… that's not in my scrolls, friend.",
        "api_error": "The Sagwan dropped his brush (API error)",
        "api_key_missing_title": "Oh dear — the Sagwan has lost his voice (ANTHROPIC_API_KEY not set)",
        "api_key_missing_body": "Create a `.env` file in the project root and add the key below, then wake Streamlit again.",
        "retry_failed": "The Sagwan keeps dozing off… please try again in a moment.",
        "original_excerpt": "Original line",
        "view_source": "🔗 View original scroll",
        "evidence_id": "Evidence",
        "rag_debug_title": "🔬 Sagwan's search notes (RAG scores)",
        "cost_title": "⏱ Sagwan's daily wage (response meta)",
        "tokens_in": "Words heard",
        "tokens_out": "Words written",
        "est_cost_krw": "Today's wage",
        "export_label": "💾 Take the scroll (JSON)",
        "reset_label": "🔄 Start over (wake the Sagwan)",
        "map_title": "🗺 Where on earth",
        "thinking": "The Sagwan is rummaging through the scrolls",
        "why_title": "Why 사초 AI?",
        "why_subtitle": "What sets us apart from generic AI",
        "why_1_t": "Click-to-verify sources",
        "why_1_d": "Every claim links to a primary Korean record (Sillok, Goryeosa, NIKH DB). Open the original yourself.",
        "why_2_t": "No single 'truth'",
        "why_2_d": "Where scholars disagree (e.g. the post-mortem embellishment debate around Jeong Mong-ju at Seonjukgyo), both views are shown.",
        "why_3_t": "Anchored to real places",
        "why_3_d": "Gyeongju, Danyang, Seoul palaces — pinned on a map, perfect when you're actually visiting.",
        "why_4_t": "Refuses to hallucinate",
        "why_4_d": "If it isn't in the records, the Sagwan says \"can't confirm.\" Trust badges (Verified / AI Narration / Inferred) on every reply.",
        "collection_btn": "📜 Scrolls seen",
        "collection_title": "Scrolls the Sagwan has shown you",
        "collection_sub": "Total scrolls met so far",
        "collection_count": "scrolls",
        "collection_empty": "No scrolls met yet…",
        "collection_empty_hint": "Ask the Sagwan something.",
        "back_to_chat": "← Back to the Sagwan",
    },
    "ja": {
        "mode_quest":   "🎮 クエスト",
        "mode_chat":    "💬 自由対話",
        "quest_intro_title":  "巻物クエスト",
        "quest_intro_desc":   "史官が韓国史の問題を出します。4択で答えて 사초(史草) を貯めましょう。",
        "quest_theme_label":  "テーマを選ぶ",
        "quest_start_btn":    "🎲 新しい問題",
        "quest_next_btn":     "➡ 次の問題",
        "quest_correct":      "✅ 正解にござる! +10 사초",
        "quest_wrong":        "❌ 残念。正解は",
        "quest_explanation":  "📜 史官の解説",
        "quest_thinking":     "史官が巻物を開いておりまする…",
        "credit_label":       "사초",
        "streak_label":       "連続",
        "accuracy_label":     "正答率",
        "map_open":           "🗺 地図で見る",
        "photo_search":       "📷 写真を探す",
        "theme_all":          "ランダム",
        "theme_palaces":      "ソウル五大宮",
        "theme_gyeongju":     "慶州(新羅)",
        "theme_danyang":      "丹陽",
        "theme_andong":       "安東",
        "theme_imjin":        "壬辰倭乱",
        "theme_joseon_kings": "朝鮮の王たち",
        "theme_colonial":     "日本統治期人物",
        "theme_historians":   "韓国史 史官・記録",
        "theme_kculture":     "🎬 Kコンテンツ × 実在地",
        "play_mode_label":     "遊び方",
        "play_mode_theme":     "🎲 自由テーマ",
        "play_mode_course":    "🗺 キュレーションコース",
        "course_label":        "コースを選ぶ",
        "course_progress":     "手がかり {n}/{total}",
        "course_score":        "正解数",
        "hint_btn":            "💡 ヒント (-3 사초)",
        "hint_used":           "💡 ヒント使用済み (誤答2つ除外)",
        "hint_locked":         "💡 ヒント (사초が3足りませぬ)",
        "option_eliminated":   "(除外)",
        "option_notes_title":  "🧠 なぜ正解で、なぜ間違いか",
        "ending_title":        "📜 コース終了 — 巻物が閉じられました",
        "ending_score_line":   "{score}/{total} 手がかりを解きました。",
        "ending_master":       "🏅 史官の頭首 — 巻物に名を残しまする",
        "ending_companion":    "🤝 史官の同行 — よき同志でござる",
        "ending_apprentice":   "📝 史官の見習い — もう一度巻物を開いてみませぬか",
        "ending_novice":       "😴 ふむ…またのお越しを",
        "ending_restart_btn":  "🔁 別のコースに挑戦",

        "placeholder": "ねむたい史官に何かお尋ねくだされ… (起きているうちに)",
        "evidence_header": "📜 史料の巻物",
        "suggested_header": "💭 こんなのはいかが…",
        "no_evidence": "うーむ…拙者の巻物には載っておりませぬ。",
        "api_error": "史官、筆を落としました (API エラー)",
        "api_key_missing_title": "うっ…史官が口を閉ざしました (ANTHROPIC_API_KEY 未設定)",
        "api_key_missing_body": "プロジェクト直下に `.env` を作って下記キーを書き入れ、Streamlit を起こし直してくだされ。",
        "retry_failed": "史官がまた眠りに落ちかけておりまする…少し後にお呼びくだされ。",
        "original_excerpt": "原文一節",
        "view_source": "🔗 原本の巻物を見る",
        "evidence_id": "証拠",
        "rag_debug_title": "🔬 史官の検索メモ (RAG スコア)",
        "cost_title": "⏱ 史官の日給 (応答メタ)",
        "tokens_in": "聞いた字",
        "tokens_out": "書いた字",
        "est_cost_krw": "本日の日給",
        "export_label": "💾 巻物を持ち帰る (JSON)",
        "reset_label": "🔄 最初から (史官も起こす)",
        "map_title": "🗺 そは何処ぞ",
        "thinking": "史官が巻物を漁っております",
        "why_title": "なぜ 사초 AI?",
        "why_subtitle": "汎用AIと違うところ",
        "why_1_t": "出典をクリックして検証",
        "why_1_d": "答えごとに朝鮮王朝実録・高麗史・韓国史DBの原典リンク。クリックして原文を直接ご確認くだされ。",
        "why_2_t": "学説は一つではない",
        "why_2_d": "鄭夢周・善竹橋の後世潤色説のように見解が分かれる事案は両論を併記。",
        "why_3_t": "場所と結びつく",
        "why_3_d": "慶州・丹陽・ソウル宮殿 — 地図ピン付きで、実際の旅先で歴史の文脈に出会える。",
        "why_4_t": "ハルシネーション拒否",
        "why_4_d": "史料に無いものは「確認できぬ」。事実確認バッジ(史料で確認/AI演出/推定)で信頼度を表示。",
        "collection_btn": "📜 見た巻物",
        "collection_title": "史官と一緒に見た巻物",
        "collection_sub": "これまでに出会った史料",
        "collection_count": "件",
        "collection_empty": "まだ出会った史料はござりませぬ…",
        "collection_empty_hint": "史官に何ぞお尋ねくだされ。",
        "back_to_chat": "← 史官のもとへ",
    },
    "zh": {
        "mode_quest":   "🎮 任务",
        "mode_chat":    "💬 自由对话",
        "quest_intro_title":  "卷子任务",
        "quest_intro_desc":   "史官出韩国史题,四选一作答,累积 사초(史草) 积分。",
        "quest_theme_label":  "选择主题",
        "quest_start_btn":    "🎲 新问题",
        "quest_next_btn":     "➡ 下一题",
        "quest_correct":      "✅ 答对了! +10 사초",
        "quest_wrong":        "❌ 可惜。正确答案是",
        "quest_explanation":  "📜 史官的解说",
        "quest_thinking":     "史官正在展开卷子…",
        "credit_label":       "사초",
        "streak_label":       "连胜",
        "accuracy_label":     "正确率",
        "map_open":           "🗺 在地图上查看",
        "photo_search":       "📷 找图片",
        "theme_all":          "随机",
        "theme_palaces":      "首尔五大宫",
        "theme_gyeongju":     "庆州(新罗)",
        "theme_danyang":      "丹阳",
        "theme_andong":       "安东",
        "theme_imjin":        "壬辰倭乱",
        "theme_joseon_kings": "朝鲜诸王",
        "theme_colonial":     "日帝时期人物",
        "theme_historians":   "韩国史·史官·史料",
        "theme_kculture":     "🎬 K内容×真实地点",
        "play_mode_label":     "玩法",
        "play_mode_theme":     "🎲 自由主题",
        "play_mode_course":    "🗺 策划路线",
        "course_label":        "选择路线",
        "course_progress":     "线索 {n}/{total}",
        "course_score":        "已答对",
        "hint_btn":            "💡 用提示 (-3 사초)",
        "hint_used":           "💡 已用提示 (排除2个错答)",
        "hint_locked":         "💡 提示 (差3 사초)",
        "option_eliminated":   "(已排除)",
        "option_notes_title":  "🧠 解析 — 为何正确,为何似是而非",
        "ending_title":        "📜 路线完成 — 卷子合上了",
        "ending_score_line":   "你解出了 {score}/{total} 条线索。",
        "ending_master":       "🏅 史官之首 — 卷子上将留下你的名字",
        "ending_companion":    "🤝 史官之伴 — 是位好同行",
        "ending_apprentice":   "📝 史官之见习 — 再翻开卷子试试",
        "ending_novice":       "😴 唔…下次再来吧",
        "ending_restart_btn":  "🔁 试试别的路线",

        "placeholder": "向犯困的小史官请教点什么吧… (趁他还醒着)",
        "evidence_header": "📜 史料卷子",
        "suggested_header": "💭 不如问问这些…",
        "no_evidence": "唔…小臣的卷子里查无此事。",
        "api_error": "史官手一抖,笔掉了 (API 错误)",
        "api_key_missing_title": "哎呀…史官闭嘴了 (未设置 ANTHROPIC_API_KEY)",
        "api_key_missing_body": "请在项目根目录创建 `.env` 文件并填入下方密钥,然后再把 Streamlit 叫醒。",
        "retry_failed": "史官又快睡着了…请稍后再呼唤。",
        "original_excerpt": "原文一句",
        "view_source": "🔗 看原本卷子",
        "evidence_id": "证据",
        "rag_debug_title": "🔬 史官的检索小抄 (RAG 得分)",
        "cost_title": "⏱ 史官的工钱 (响应元数据)",
        "tokens_in": "听到的字",
        "tokens_out": "写下的字",
        "est_cost_krw": "今日工钱",
        "export_label": "💾 带走这卷对话 (JSON)",
        "reset_label": "🔄 从头来过 (顺便叫醒史官)",
        "map_title": "🗺 此地何处",
        "thinking": "史官正在翻卷子",
        "why_title": "为何选 사초 AI?",
        "why_subtitle": "与通用AI的区别",
        "why_1_t": "点击核验出处",
        "why_1_d": "每条答复都附朝鲜王朝实录·高丽史·韩国史DB等原典链接,可点开亲自核对。",
        "why_2_t": "不止一种说法",
        "why_2_d": "如郑梦周善竹桥死亡的后世润色说,学界有争议的议题会并列双方观点。",
        "why_3_t": "与实地相连",
        "why_3_d": "庆州·丹阳·首尔宫阙 — 地图标点,旅行途中即可对照历史脉络。",
        "why_4_t": "拒绝胡编",
        "why_4_d": "史料未载之事会说\"无从核实\"。每条答复带有信任徽章(史料确认/AI演绎/推断)。",
        "collection_btn": "📜 已见卷子",
        "collection_title": "与史官一同看过的卷子",
        "collection_sub": "迄今遇到的史料",
        "collection_count": "卷",
        "collection_empty": "尚未遇到任何史料…",
        "collection_empty_hint": "随便问史官点什么吧。",
        "back_to_chat": "← 回到史官那里",
    },
}
