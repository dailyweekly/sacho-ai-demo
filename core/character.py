"""하찮은 사관(史官) 캐릭터 SVG 자산 — 요시타케 신스케 풍.

특징:
- 콩알 같은 둥글둥글 몸·머리, 점 두 개 눈, 부드러운 곡선
- 크림/베이지 톤 + 무광 잉크 라인
- 표정·동작별 7종 + 무드 아이콘 3종

UI 곳곳에 산재시킨다 (헤더, 빈 화면, 추천 카드, footer, 여백 데코, thinking, 에러).
"""
from __future__ import annotations


# ─────────────────────────────────────────────────────────────
# 메인 (대형) — 졸린 사관, 두루마리 안고 있음
# ─────────────────────────────────────────────────────────────
MAIN_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 170 200" width="150" height="176" aria-label="졸린 사관">
  <!-- shadow -->
  <ellipse cx="85" cy="192" rx="44" ry="4" fill="#2A1F18" opacity="0.12"/>

  <!-- body (배 모양) -->
  <path d="M40 184 Q34 142 50 122 Q85 110 120 122 Q136 142 130 184 Q85 192 40 184 Z"
        fill="#FDF8EE" stroke="#2A1F18" stroke-width="3" stroke-linejoin="round"/>
  <!-- sash -->
  <path d="M46 158 Q85 162 124 158 L122 168 Q85 170 48 168 Z"
        fill="#C97064" stroke="#2A1F18" stroke-width="2"/>

  <!-- arms (stubs) -->
  <ellipse cx="42" cy="152" rx="9" ry="14" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <ellipse cx="128" cy="152" rx="9" ry="14" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>

  <!-- scroll -->
  <rect x="50" y="164" width="70" height="14" rx="6" fill="#FFF6E0" stroke="#2A1F18" stroke-width="2.2"/>
  <circle cx="50" cy="171" r="4" fill="#D8C28A" stroke="#2A1F18" stroke-width="1.6"/>
  <circle cx="120" cy="171" r="4" fill="#D8C28A" stroke="#2A1F18" stroke-width="1.6"/>
  <line x1="57" y1="170" x2="113" y2="170" stroke="#2A1F18" stroke-width="0.6" opacity="0.4"/>
  <line x1="57" y1="174" x2="108" y2="174" stroke="#2A1F18" stroke-width="0.6" opacity="0.4"/>

  <!-- head (oversized round) -->
  <ellipse cx="85" cy="68" rx="48" ry="44" fill="#FDF8EE" stroke="#2A1F18" stroke-width="3"/>

  <!-- gat brim -->
  <ellipse cx="85" cy="28" rx="58" ry="5" fill="#2A1F18"/>
  <!-- gat crown -->
  <path d="M58 28 Q56 4 85 2 Q114 4 112 28 Z" fill="#2A1F18"/>
  <!-- gat shine -->
  <ellipse cx="76" cy="12" rx="4" ry="2.2" fill="#5A4338" opacity="0.7"/>
  <!-- gat string -->
  <path d="M58 30 Q50 62 76 80" stroke="#2A1F18" stroke-width="1.4" fill="none"/>
  <path d="M112 30 Q120 62 94 80" stroke="#2A1F18" stroke-width="1.4" fill="none"/>

  <!-- sleepy eyes (closed curves) -->
  <path d="M64 66 Q68 70 72 66" stroke="#2A1F18" stroke-width="2.8" fill="none" stroke-linecap="round"/>
  <path d="M98 66 Q102 70 106 66" stroke="#2A1F18" stroke-width="2.8" fill="none" stroke-linecap="round"/>

  <!-- blush -->
  <ellipse cx="56" cy="82" rx="6" ry="3.2" fill="#F2B5B5" opacity="0.7"/>
  <ellipse cx="114" cy="82" rx="6" ry="3.2" fill="#F2B5B5" opacity="0.7"/>

  <!-- mouth (tiny) -->
  <path d="M80 90 Q85 93 90 90" stroke="#2A1F18" stroke-width="2" fill="none" stroke-linecap="round"/>

  <!-- floating dust -->
  <circle cx="150" cy="54" r="1.8" fill="#B89A6F" opacity="0.55"/>
  <circle cx="156" cy="72" r="1.3" fill="#B89A6F" opacity="0.45"/>
  <circle cx="14" cy="86" r="1.6" fill="#B89A6F" opacity="0.5"/>
  <circle cx="20" cy="60" r="1.2" fill="#B89A6F" opacity="0.4"/>

  <!-- snore z -->
  <text x="124" y="38" font-family="Georgia,serif" font-size="14" font-style="italic" fill="#8B7A60" opacity="0.7">z</text>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# 로고 — 머리+갓만 (40px)
# ─────────────────────────────────────────────────────────────
LOGO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 54 56" width="44" height="46" aria-label="사관 로고">
  <ellipse cx="27" cy="34" rx="20" ry="18" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.6"/>
  <ellipse cx="27" cy="14" rx="24" ry="3.2" fill="#2A1F18"/>
  <path d="M16 14 Q15 2 27 1 Q39 2 38 14 Z" fill="#2A1F18"/>
  <circle cx="21" cy="33" r="2.2" fill="#2A1F18"/>
  <circle cx="33" cy="33" r="2.2" fill="#2A1F18"/>
  <ellipse cx="16" cy="40" rx="2.6" ry="1.5" fill="#F2B5B5" opacity="0.7"/>
  <ellipse cx="38" cy="40" rx="2.6" ry="1.5" fill="#F2B5B5" opacity="0.7"/>
  <path d="M24 42 Q27 44 30 42" stroke="#2A1F18" stroke-width="1.6" fill="none" stroke-linecap="round"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# 자고 있는 사관 — 빈 화면·에러용
# ─────────────────────────────────────────────────────────────
SLEEPING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 84" width="120" height="72" aria-label="자는 사관">
  <ellipse cx="70" cy="78" rx="50" ry="3" fill="#2A1F18" opacity="0.1"/>
  <!-- body lying -->
  <ellipse cx="78" cy="56" rx="48" ry="16" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <!-- head -->
  <ellipse cx="32" cy="48" rx="25" ry="22" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <!-- gat tilted -->
  <g transform="rotate(-15 24 32)">
    <ellipse cx="24" cy="32" rx="30" ry="3.4" fill="#2A1F18"/>
    <path d="M10 32 Q10 14 24 12 Q38 14 38 32 Z" fill="#2A1F18"/>
  </g>
  <!-- closed eye line -->
  <path d="M22 50 L28 50" stroke="#2A1F18" stroke-width="2" stroke-linecap="round"/>
  <!-- snoring mouth -->
  <ellipse cx="42" cy="54" rx="2.2" ry="3" fill="#2A1F18"/>
  <!-- blush -->
  <ellipse cx="18" cy="58" rx="3.2" ry="1.6" fill="#F2B5B5" opacity="0.7"/>
  <!-- z z z -->
  <text x="68" y="22" font-family="Georgia,serif" font-size="18" font-style="italic" fill="#8B7A60">z</text>
  <text x="84" y="14" font-family="Georgia,serif" font-size="14" font-style="italic" fill="#8B7A60" opacity="0.75">z</text>
  <text x="98" y="8"  font-family="Georgia,serif" font-size="10" font-style="italic" fill="#8B7A60" opacity="0.55">z</text>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# 걸어가는 사관 — thinking 인디케이터, footer
# ─────────────────────────────────────────────────────────────
WALKING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 82" width="44" height="60" aria-label="걷는 사관">
  <line x1="24" y1="62" x2="20" y2="76" stroke="#2A1F18" stroke-width="3" stroke-linecap="round"/>
  <line x1="36" y1="62" x2="42" y2="76" stroke="#2A1F18" stroke-width="3" stroke-linecap="round"/>
  <ellipse cx="30" cy="52" rx="17" ry="14" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <!-- arm with scroll -->
  <ellipse cx="46" cy="50" rx="5" ry="8" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2"/>
  <rect x="40" y="50" width="14" height="6" rx="3" fill="#FFF6E0" stroke="#2A1F18" stroke-width="1.5"/>
  <!-- head -->
  <ellipse cx="30" cy="28" rx="19" ry="17" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <!-- gat -->
  <ellipse cx="30" cy="11" rx="24" ry="3" fill="#2A1F18"/>
  <path d="M20 11 Q20 1 30 0 Q40 1 40 11 Z" fill="#2A1F18"/>
  <!-- eyes -->
  <circle cx="24" cy="28" r="1.8" fill="#2A1F18"/>
  <circle cx="36" cy="28" r="1.8" fill="#2A1F18"/>
  <!-- mouth (open o) -->
  <ellipse cx="30" cy="36" rx="1.2" ry="1.5" fill="#2A1F18"/>
  <!-- blush -->
  <ellipse cx="20" cy="34" rx="2" ry="1.2" fill="#F2B5B5" opacity="0.7"/>
  <ellipse cx="40" cy="34" rx="2" ry="1.2" fill="#F2B5B5" opacity="0.7"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# 손가락 든 사관 — 안내/추천
# ─────────────────────────────────────────────────────────────
POINTING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 84" width="58" height="60" aria-label="안내하는 사관">
  <!-- body -->
  <ellipse cx="38" cy="60" rx="20" ry="17" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <!-- raised arm -->
  <path d="M54 52 L66 28" stroke="#2A1F18" stroke-width="3" fill="none" stroke-linecap="round"/>
  <circle cx="66" cy="26" r="4" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2"/>
  <!-- head -->
  <ellipse cx="36" cy="32" rx="21" ry="19" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <!-- gat -->
  <ellipse cx="36" cy="13" rx="26" ry="3.2" fill="#2A1F18"/>
  <path d="M24 13 Q24 2 36 1 Q48 2 48 13 Z" fill="#2A1F18"/>
  <!-- eyes (looking up-right) -->
  <ellipse cx="30" cy="30" rx="2" ry="2.6" fill="#2A1F18"/>
  <ellipse cx="42" cy="30" rx="2" ry="2.6" fill="#2A1F18"/>
  <!-- mouth small smile -->
  <path d="M33 40 Q37 42 41 40" stroke="#2A1F18" stroke-width="1.8" fill="none" stroke-linecap="round"/>
  <!-- blush -->
  <ellipse cx="24" cy="38" rx="3" ry="1.6" fill="#F2B5B5" opacity="0.7"/>
  <ellipse cx="48" cy="38" rx="3" ry="1.6" fill="#F2B5B5" opacity="0.7"/>
  <!-- sparkle on fingertip -->
  <path d="M66 19 L67.5 23 L71 24 L67.5 25 L66 29 L64.5 25 L61 24 L64.5 23 Z" fill="#FFD55A" stroke="#2A1F18" stroke-width="0.8"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# 머리 갸우뚱 사관 — 의아할 때 (확인 불가/추천 카드)
# ─────────────────────────────────────────────────────────────
CONFUSED_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 84" width="58" height="60" aria-label="갸우뚱한 사관">
  <text x="56" y="22" font-family="Georgia,serif" font-size="24" font-weight="bold" fill="#C97064">?</text>
  <ellipse cx="36" cy="60" rx="20" ry="17" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <g transform="rotate(-14 36 38)">
    <ellipse cx="36" cy="38" rx="21" ry="19" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
    <ellipse cx="36" cy="20" rx="26" ry="3.2" fill="#2A1F18"/>
    <path d="M24 20 Q24 8 36 7 Q48 8 48 20 Z" fill="#2A1F18"/>
    <circle cx="30" cy="38" r="2.2" fill="#2A1F18"/>
    <circle cx="42" cy="38" r="2.2" fill="#2A1F18"/>
    <path d="M30 48 Q33 46 36 48 Q39 50 42 48" stroke="#2A1F18" stroke-width="1.8" fill="none" stroke-linecap="round"/>
    <ellipse cx="24" cy="44" rx="3" ry="1.6" fill="#F2B5B5" opacity="0.7"/>
    <ellipse cx="48" cy="44" rx="3" ry="1.6" fill="#F2B5B5" opacity="0.7"/>
  </g>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# 하품하는 사관 — 추천 카드 변형 / 데코
# ─────────────────────────────────────────────────────────────
YAWNING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 84" width="58" height="60" aria-label="하품하는 사관">
  <ellipse cx="40" cy="62" rx="20" ry="17" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <ellipse cx="40" cy="34" rx="21" ry="19" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <ellipse cx="40" cy="16" rx="26" ry="3.2" fill="#2A1F18"/>
  <path d="M28 16 Q28 4 40 3 Q52 4 52 16 Z" fill="#2A1F18"/>
  <!-- closed eyes -->
  <path d="M30 32 L36 32" stroke="#2A1F18" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M44 32 L50 32" stroke="#2A1F18" stroke-width="2.4" stroke-linecap="round"/>
  <!-- yawning mouth -->
  <ellipse cx="40" cy="46" rx="4.5" ry="6.5" fill="#2A1F18"/>
  <ellipse cx="40" cy="48" rx="3" ry="4" fill="#C97064"/>
  <!-- blush -->
  <ellipse cx="26" cy="42" rx="3" ry="1.6" fill="#F2B5B5" opacity="0.7"/>
  <ellipse cx="54" cy="42" rx="3" ry="1.6" fill="#F2B5B5" opacity="0.7"/>
  <!-- hand near mouth (stub) -->
  <ellipse cx="56" cy="44" rx="6" ry="9" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2"/>
  <!-- z -->
  <text x="62" y="14" font-family="Georgia,serif" font-size="14" font-style="italic" fill="#8B7A60" opacity="0.7">z</text>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# 사관 머리만 빼꼼 — 우측 여백 데코
# ─────────────────────────────────────────────────────────────
PEEKING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 80" width="48" height="60" aria-label="빼꼼 사관">
  <ellipse cx="40" cy="48" rx="24" ry="22" fill="#FDF8EE" stroke="#2A1F18" stroke-width="2.5"/>
  <ellipse cx="40" cy="28" rx="28" ry="3.4" fill="#2A1F18"/>
  <path d="M28 28 Q28 12 40 10 Q52 12 52 28 Z" fill="#2A1F18"/>
  <circle cx="33" cy="48" r="2.6" fill="#2A1F18"/>
  <circle cx="45" cy="48" r="2.6" fill="#2A1F18"/>
  <ellipse cx="24" cy="56" rx="3.4" ry="1.8" fill="#F2B5B5" opacity="0.7"/>
  <path d="M37 56 Q40 58 43 56" stroke="#2A1F18" stroke-width="1.8" fill="none" stroke-linecap="round"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# 4컷 추천 카드용 캐릭터 풀
# ─────────────────────────────────────────────────────────────
SUGGEST_CHARS = [POINTING_SVG, CONFUSED_SVG, WALKING_SVG, YAWNING_SVG]


# 하위 호환 — 기존 import 보호
SAGWAN_SVG_FULL = MAIN_SVG
SAGWAN_SVG_MINI = LOGO_SVG


# ─────────────────────────────────────────────────────────────
# 표정 아이콘 (배지 스티커용)
# ─────────────────────────────────────────────────────────────
_MOOD_SPARKLE = """
<svg viewBox="0 0 24 24" width="18" height="18">
  <path d="M12 2 L13.6 8.6 L20 10 L13.6 11.4 L12 18 L10.4 11.4 L4 10 L10.4 8.6 Z"
        fill="#FFD55A" stroke="#2A1F18" stroke-width="1.4" stroke-linejoin="round"/>
  <circle cx="19" cy="6" r="1.6" fill="#FFD55A" stroke="#2A1F18" stroke-width="1"/>
  <circle cx="6" cy="19" r="1.3" fill="#FFD55A" stroke="#2A1F18" stroke-width="1"/>
</svg>
"""

_MOOD_BRUSH = """
<svg viewBox="0 0 24 24" width="18" height="18">
  <path d="M19 3 L21 5 L9 17 L5 21 Q3 21 3 19 L7 15 Z"
        fill="#FFF6E0" stroke="#2A1F18" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M5 21 Q3 19 5 17" stroke="#2A1F18" stroke-width="1.5" fill="#C97064" stroke-linejoin="round"/>
</svg>
"""

_MOOD_CLOUD = """
<svg viewBox="0 0 24 24" width="18" height="18">
  <path d="M7 17 Q3 17 3 14 Q3 11 6.5 11 Q7 7 11 7 Q15 7 15.5 11 Q19 11 19 14 Q19 17 16 17 Z"
        fill="#D7E4EF" stroke="#2A1F18" stroke-width="1.5" stroke-linejoin="round"/>
  <circle cx="9.5" cy="14.5" r="0.9" fill="#2A1F18"/>
  <circle cx="13" cy="14.5" r="0.9" fill="#2A1F18"/>
</svg>
"""

MOOD_ICON = {
    "사료 확인됨": _MOOD_SPARKLE,
    "AI 각색":   _MOOD_BRUSH,
    "추정":      _MOOD_CLOUD,
}
