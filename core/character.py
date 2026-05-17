"""사관 캐릭터 — 사용자 제공 그림책 풍 PNG (assets/c_*.png).

assets/c_*.png 16종 포즈를 base64 데이터 URI로 래핑해 그대로 <img> 로 임베드.
SVG fallback도 함께 노출 (호환성).
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path


_ASSETS = Path(__file__).resolve().parents[1] / "assets"


@lru_cache(maxsize=32)
def char_img(name: str, width: int | None = None, css_class: str = "") -> str:
    """assets/c_<name>.png 를 base64 <img> 태그로 반환.

    name : 포즈 이름 (start, writing, cheek, books, proud, facedown,
                     paper, reading, umbrella, happy, candle, moon,
                     peeking, snack, sleeping, cheer)
    width: 선택 — px 단위. 미지정 시 원본 비율로 자동.
    css_class: 추가 CSS 클래스 (애니메이션 적용 등).
    """
    path = _ASSETS / f"c_{name}.png"
    if not path.exists():
        return f'<span style="color:#C97064;">[missing c_{name}]</span>'
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    size_attr = f' style="width:{width}px;height:auto;"' if width else ''
    cls = f' class="{css_class}"' if css_class else ''
    return (
        f'<img src="data:image/png;base64,{b64}" alt="사관 {name}"'
        f'{cls}{size_attr}>'
    )


@lru_cache(maxsize=16)
def course_thumb(course_id: str, width: int | None = None,
                 css_class: str = "") -> str:
    """assets/course_<course_id>.png 코스 썸네일 base64 <img> 반환.

    파일 없으면 빈 문자열 (graceful — UI 가 자연스럽게 미노출).
    """
    path = _ASSETS / f"course_{course_id}.png"
    if not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    size_attr = f' style="width:{width}px;height:auto;"' if width else ''
    cls = f' class="course-thumb {css_class}"'.rstrip()
    return (
        f'<img src="data:image/png;base64,{b64}" alt="코스 {course_id}"'
        f'{cls}{size_attr}>'
    )


# 팔레트 (참고용 주석 — SVG에는 hex 직접 박음)
#   SKIN        #FBF1DD   얼굴·손
#   HANBOK      #D67B5A   한복 (코랄)
#   HANBOK_DK   #B05E42   한복 음영
#   HAIR/INK    #3A2A1F   머리·외곽선 (따뜻한 다크 브라운)
#   EMBLEM_OUT  #FFE090   흉배 외곽
#   EMBLEM_IN   #E2B574   흉배 내부
#   BLUSH       #F4B0A0   볼
#   PAPER       #FFF6E0   두루마리
#   GOLD        #DBB871   금속 (자물쇠)


# ─────────────────────────────────────────────────────────────
# MAIN — 큰 사관 (헤더·게이트·빈 화면 hero)
# ─────────────────────────────────────────────────────────────
MAIN_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 170 200" width="150" height="176" aria-label="sagwan main">
  <ellipse cx="85" cy="194" rx="60" ry="4" fill="#3A2A1F" opacity="0.12"/>
  <!-- 통통하게 한 덩어리로 만든 동글동글 몸 (어깨 따로 안 그림) -->
  <path d="M22 192
           Q10 168 14 140
           Q18 116 44 108
           Q85 102 126 108
           Q152 116 156 140
           Q160 168 148 192
           Q85 204 22 192 Z"
        fill="#D67B5A" stroke="#3A2A1F" stroke-width="3" stroke-linejoin="round"/>
  <!-- 바닥쪽 음영 (둥근 배 강조) -->
  <path d="M30 184 Q85 196 140 184 Q134 198 85 202 Q36 198 30 184 Z"
        fill="#B05E42" opacity="0.35"/>
  <!-- 흉배 (가운데) -->
  <circle cx="85" cy="148" r="13" fill="#FFE090" stroke="#3A2A1F" stroke-width="1.8"/>
  <circle cx="85" cy="148" r="7" fill="#E2B574" stroke="#3A2A1F" stroke-width="1.2"/>
  <!-- 작은 손 두 개가 앞에서 두루마리 잡고 있음 -->
  <rect x="42" y="166" width="86" height="13" rx="6" fill="#FFF6E0" stroke="#3A2A1F" stroke-width="2"/>
  <line x1="50" y1="170" x2="120" y2="170" stroke="#3A2A1F" stroke-width="0.6" opacity="0.4"/>
  <line x1="50" y1="175" x2="115" y2="175" stroke="#3A2A1F" stroke-width="0.6" opacity="0.4"/>
  <circle cx="40" cy="172" r="7" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2"/>
  <circle cx="130" cy="172" r="7" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2"/>
  <!-- 머리 -->
  <ellipse cx="85" cy="72" rx="46" ry="42" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="3"/>
  <!-- 머리카락 -->
  <path d="M41 72 Q41 38 85 34 Q129 38 129 72 Q127 58 85 56 Q43 58 41 72 Z" fill="#3A2A1F"/>
  <!-- 상투 -->
  <ellipse cx="85" cy="28" rx="14" ry="11" fill="#3A2A1F" stroke="#2A1F18" stroke-width="2"/>
  <ellipse cx="85" cy="24" rx="6" ry="3" fill="#5A4438" opacity="0.5"/>
  <!-- 눈 (점) -->
  <circle cx="69" cy="74" r="3" fill="#3A2A1F"/>
  <circle cx="101" cy="74" r="3" fill="#3A2A1F"/>
  <!-- 볼터치 -->
  <ellipse cx="57" cy="86" rx="6" ry="3" fill="#F4B0A0" opacity="0.7"/>
  <ellipse cx="113" cy="86" rx="6" ry="3" fill="#F4B0A0" opacity="0.7"/>
  <!-- 입 -->
  <path d="M79 94 Q85 98 91 94" stroke="#3A2A1F" stroke-width="2" fill="none" stroke-linecap="round"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# LOGO — 머리만 (톱바)
# ─────────────────────────────────────────────────────────────
LOGO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60" width="44" height="44" aria-label="sagwan logo">
  <ellipse cx="30" cy="38" rx="22" ry="20" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2.5"/>
  <path d="M9 38 Q9 16 30 14 Q51 16 51 38 Q50 28 30 26 Q10 28 9 38 Z" fill="#3A2A1F"/>
  <ellipse cx="30" cy="10" rx="8" ry="6" fill="#3A2A1F" stroke="#2A1F18" stroke-width="1.5"/>
  <circle cx="22" cy="40" r="1.8" fill="#3A2A1F"/>
  <circle cx="38" cy="40" r="1.8" fill="#3A2A1F"/>
  <ellipse cx="16" cy="47" rx="2.6" ry="1.4" fill="#F4B0A0" opacity="0.7"/>
  <ellipse cx="44" cy="47" rx="2.6" ry="1.4" fill="#F4B0A0" opacity="0.7"/>
  <path d="M27 50 Q30 52 33 50" stroke="#3A2A1F" stroke-width="1.4" fill="none" stroke-linecap="round"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# SLEEPING — 누워서 자는 사관
# ─────────────────────────────────────────────────────────────
SLEEPING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 88" width="128" height="75" aria-label="sleeping sagwan">
  <ellipse cx="80" cy="80" rx="58" ry="4" fill="#3A2A1F" opacity="0.1"/>
  <!-- 누워있는 통통 몸 (한 덩어리) -->
  <ellipse cx="86" cy="60" rx="54" ry="20" fill="#D67B5A" stroke="#3A2A1F" stroke-width="2.5"/>
  <path d="M40 64 Q86 76 132 64 Q126 80 86 82 Q44 80 40 64 Z" fill="#B05E42" opacity="0.35"/>
  <circle cx="86" cy="60" r="7" fill="#FFE090" stroke="#3A2A1F" stroke-width="1.5"/>
  <!-- 머리 -->
  <ellipse cx="32" cy="50" rx="24" ry="22" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2.5"/>
  <path d="M9 50 Q9 26 32 22 Q55 26 55 50 Q54 38 32 36 Q10 38 9 50 Z" fill="#3A2A1F"/>
  <g transform="rotate(-14 28 18)">
    <ellipse cx="28" cy="18" rx="9" ry="6" fill="#3A2A1F" stroke="#2A1F18" stroke-width="1.5"/>
  </g>
  <path d="M24 52 L30 52" stroke="#3A2A1F" stroke-width="2" stroke-linecap="round"/>
  <ellipse cx="42" cy="56" rx="2" ry="2.6" fill="#3A2A1F"/>
  <ellipse cx="20" cy="59" rx="3" ry="1.5" fill="#F4B0A0" opacity="0.7"/>
  <text x="64" y="22" font-family="Georgia,serif" font-size="18" font-style="italic" fill="#8B7A60">z</text>
  <text x="80" y="14" font-family="Georgia,serif" font-size="14" font-style="italic" fill="#8B7A60" opacity="0.75">z</text>
  <text x="94" y="8"  font-family="Georgia,serif" font-size="10" font-style="italic" fill="#8B7A60" opacity="0.55">z</text>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# WALKING — 걷는 사관 (thinking·footer)
# ─────────────────────────────────────────────────────────────
WALKING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 86" width="46" height="62" aria-label="walking sagwan">
  <line x1="26" y1="68" x2="22" y2="80" stroke="#3A2A1F" stroke-width="3" stroke-linecap="round"/>
  <line x1="38" y1="68" x2="44" y2="80" stroke="#3A2A1F" stroke-width="3" stroke-linecap="round"/>
  <!-- 통통한 몸 -->
  <ellipse cx="32" cy="54" rx="22" ry="17" fill="#D67B5A" stroke="#3A2A1F" stroke-width="2.5"/>
  <circle cx="32" cy="54" r="5" fill="#FFE090" stroke="#3A2A1F" stroke-width="1.4"/>
  <!-- 머리 -->
  <ellipse cx="32" cy="28" rx="20" ry="18" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2.5"/>
  <path d="M12 28 Q12 8 32 6 Q52 8 52 28 Q50 20 32 18 Q14 20 12 28 Z" fill="#3A2A1F"/>
  <ellipse cx="32" cy="4" rx="7" ry="5" fill="#3A2A1F" stroke="#2A1F18" stroke-width="1.5"/>
  <circle cx="26" cy="30" r="1.8" fill="#3A2A1F"/>
  <circle cx="38" cy="30" r="1.8" fill="#3A2A1F"/>
  <ellipse cx="32" cy="38" rx="1.2" ry="1.5" fill="#3A2A1F"/>
  <ellipse cx="22" cy="36" rx="2" ry="1.2" fill="#F4B0A0" opacity="0.7"/>
  <ellipse cx="42" cy="36" rx="2" ry="1.2" fill="#F4B0A0" opacity="0.7"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# POINTING — 손가락 들어 안내하는 사관 (추천 카드·인사)
# ─────────────────────────────────────────────────────────────
POINTING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 84" width="58" height="60" aria-label="pointing sagwan">
  <ellipse cx="38" cy="58" rx="20" ry="17" fill="#D67B5A" stroke="#3A2A1F" stroke-width="2.5"/>
  <circle cx="38" cy="58" r="5" fill="#FFE090" stroke="#3A2A1F" stroke-width="1.4"/>
  <path d="M54 50 L66 26" stroke="#3A2A1F" stroke-width="3" fill="none" stroke-linecap="round"/>
  <circle cx="66" cy="24" r="4" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2"/>
  <ellipse cx="36" cy="30" rx="20" ry="18" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2.5"/>
  <path d="M16 30 Q16 8 36 6 Q56 8 56 30 Q54 18 36 16 Q18 18 16 30 Z" fill="#3A2A1F"/>
  <ellipse cx="36" cy="4" rx="8" ry="5.5" fill="#3A2A1F" stroke="#2A1F18" stroke-width="1.5"/>
  <ellipse cx="30" cy="32" rx="2" ry="2.6" fill="#3A2A1F"/>
  <ellipse cx="42" cy="32" rx="2" ry="2.6" fill="#3A2A1F"/>
  <path d="M33 40 Q36 42 39 40" stroke="#3A2A1F" stroke-width="1.6" fill="none" stroke-linecap="round"/>
  <ellipse cx="24" cy="38" rx="3" ry="1.6" fill="#F4B0A0" opacity="0.7"/>
  <ellipse cx="48" cy="38" rx="3" ry="1.6" fill="#F4B0A0" opacity="0.7"/>
  <path d="M66 17 L67.5 21 L71 22 L67.5 23 L66 27 L64.5 23 L61 22 L64.5 21 Z" fill="#FFD55A" stroke="#3A2A1F" stroke-width="0.8"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# CONFUSED — 갸우뚱 사관
# ─────────────────────────────────────────────────────────────
CONFUSED_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 84" width="58" height="60" aria-label="confused sagwan">
  <text x="58" y="22" font-family="Georgia,serif" font-size="22" font-weight="bold" fill="#C97064">?</text>
  <ellipse cx="36" cy="60" rx="20" ry="17" fill="#D67B5A" stroke="#3A2A1F" stroke-width="2.5"/>
  <circle cx="36" cy="60" r="5" fill="#FFE090" stroke="#3A2A1F" stroke-width="1.4"/>
  <g transform="rotate(-12 36 36)">
    <ellipse cx="36" cy="36" rx="20" ry="18" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2.5"/>
    <path d="M16 36 Q16 14 36 12 Q56 14 56 36 Q54 24 36 22 Q18 24 16 36 Z" fill="#3A2A1F"/>
    <ellipse cx="36" cy="10" rx="8" ry="5.5" fill="#3A2A1F" stroke="#2A1F18" stroke-width="1.5"/>
    <circle cx="30" cy="38" r="2.2" fill="#3A2A1F"/>
    <circle cx="42" cy="38" r="2.2" fill="#3A2A1F"/>
    <path d="M30 46 Q33 44 36 46 Q39 48 42 46" stroke="#3A2A1F" stroke-width="1.6" fill="none" stroke-linecap="round"/>
    <ellipse cx="24" cy="44" rx="3" ry="1.6" fill="#F4B0A0" opacity="0.7"/>
    <ellipse cx="48" cy="44" rx="3" ry="1.6" fill="#F4B0A0" opacity="0.7"/>
  </g>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# YAWNING — 하품 사관
# ─────────────────────────────────────────────────────────────
YAWNING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 84" width="58" height="60" aria-label="yawning sagwan">
  <ellipse cx="40" cy="62" rx="20" ry="17" fill="#D67B5A" stroke="#3A2A1F" stroke-width="2.5"/>
  <circle cx="40" cy="62" r="5" fill="#FFE090" stroke="#3A2A1F" stroke-width="1.4"/>
  <ellipse cx="40" cy="34" rx="20" ry="18" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2.5"/>
  <path d="M20 34 Q20 12 40 10 Q60 12 60 34 Q58 22 40 20 Q22 22 20 34 Z" fill="#3A2A1F"/>
  <ellipse cx="40" cy="8" rx="8" ry="5.5" fill="#3A2A1F" stroke="#2A1F18" stroke-width="1.5"/>
  <path d="M30 32 L36 32" stroke="#3A2A1F" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M44 32 L50 32" stroke="#3A2A1F" stroke-width="2.2" stroke-linecap="round"/>
  <ellipse cx="40" cy="44" rx="4.5" ry="6" fill="#3A2A1F"/>
  <ellipse cx="40" cy="46" rx="3" ry="4" fill="#C97064"/>
  <ellipse cx="26" cy="42" rx="3" ry="1.6" fill="#F4B0A0" opacity="0.7"/>
  <ellipse cx="54" cy="42" rx="3" ry="1.6" fill="#F4B0A0" opacity="0.7"/>
  <ellipse cx="56" cy="44" rx="5" ry="8" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2"/>
  <text x="62" y="14" font-family="Georgia,serif" font-size="14" font-style="italic" fill="#8B7A60" opacity="0.7">z</text>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# PEEKING — 머리만 빼꼼
# ─────────────────────────────────────────────────────────────
PEEKING_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 80" width="48" height="60" aria-label="peeking sagwan">
  <ellipse cx="38" cy="48" rx="24" ry="22" fill="#FBF1DD" stroke="#3A2A1F" stroke-width="2.5"/>
  <path d="M14 48 Q14 22 38 20 Q62 22 62 48 Q60 36 38 34 Q16 36 14 48 Z" fill="#3A2A1F"/>
  <ellipse cx="38" cy="16" rx="9" ry="6" fill="#3A2A1F" stroke="#2A1F18" stroke-width="1.5"/>
  <circle cx="32" cy="50" r="2.4" fill="#3A2A1F"/>
  <circle cx="44" cy="50" r="2.4" fill="#3A2A1F"/>
  <ellipse cx="24" cy="58" rx="3.2" ry="1.6" fill="#F4B0A0" opacity="0.7"/>
  <path d="M35 58 Q38 60 41 58" stroke="#3A2A1F" stroke-width="1.6" fill="none" stroke-linecap="round"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# LOCK — 자물쇠 (게이트 데코)
# ─────────────────────────────────────────────────────────────
LOCK_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 100" width="64" height="80" aria-label="lock">
  <path d="M22 50 Q22 18 40 18 Q58 18 58 50" fill="none" stroke="#3A2A1F" stroke-width="3" stroke-linecap="round"/>
  <rect x="12" y="48" width="56" height="44" rx="8" fill="#DBB871" stroke="#3A2A1F" stroke-width="3"/>
  <rect x="16" y="52" width="48" height="7" rx="3" fill="#FFE7A0" opacity="0.7"/>
  <circle cx="40" cy="66" r="5" fill="#3A2A1F"/>
  <path d="M40 69 L40 80" stroke="#3A2A1F" stroke-width="4" stroke-linecap="round"/>
</svg>
"""


# ─────────────────────────────────────────────────────────────
# 보조 / 호환
# ─────────────────────────────────────────────────────────────
# 게이트는 MAIN + LOCK 을 별도로 쓰지만, 이전 import 보호용 alias 유지
SHUSH_SVG = MAIN_SVG

SUGGEST_CHARS = [POINTING_SVG, CONFUSED_SVG, WALKING_SVG, YAWNING_SVG]

SAGWAN_SVG_FULL = MAIN_SVG
SAGWAN_SVG_MINI = LOGO_SVG


# ─────────────────────────────────────────────────────────────
# 표정 아이콘 (배지 스티커용)
# ─────────────────────────────────────────────────────────────
_MOOD_SPARKLE = """
<svg viewBox="0 0 24 24" width="18" height="18">
  <path d="M12 2 L13.6 8.6 L20 10 L13.6 11.4 L12 18 L10.4 11.4 L4 10 L10.4 8.6 Z"
        fill="#FFD55A" stroke="#3A2A1F" stroke-width="1.4" stroke-linejoin="round"/>
  <circle cx="19" cy="6" r="1.6" fill="#FFD55A" stroke="#3A2A1F" stroke-width="1"/>
  <circle cx="6" cy="19" r="1.3" fill="#FFD55A" stroke="#3A2A1F" stroke-width="1"/>
</svg>
"""

_MOOD_BRUSH = """
<svg viewBox="0 0 24 24" width="18" height="18">
  <path d="M19 3 L21 5 L9 17 L5 21 Q3 21 3 19 L7 15 Z"
        fill="#FFF6E0" stroke="#3A2A1F" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M5 21 Q3 19 5 17" stroke="#3A2A1F" stroke-width="1.5" fill="#C97064" stroke-linejoin="round"/>
</svg>
"""

_MOOD_CLOUD = """
<svg viewBox="0 0 24 24" width="18" height="18">
  <path d="M7 17 Q3 17 3 14 Q3 11 6.5 11 Q7 7 11 7 Q15 7 15.5 11 Q19 11 19 14 Q19 17 16 17 Z"
        fill="#D7E4EF" stroke="#3A2A1F" stroke-width="1.5" stroke-linejoin="round"/>
  <circle cx="9.5" cy="14.5" r="0.9" fill="#3A2A1F"/>
  <circle cx="13" cy="14.5" r="0.9" fill="#3A2A1F"/>
</svg>
"""

MOOD_ICON = {
    "사료 확인됨": _MOOD_SPARKLE,
    "AI 각색":   _MOOD_BRUSH,
    "추정":      _MOOD_CLOUD,
}
