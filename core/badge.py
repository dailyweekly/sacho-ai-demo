"""사실 확인 배지 파서.

LLM 응답 첫 줄에 다음 형태의 JSON 블록이 포함:
```badge
{"badge": "사료 확인됨" | "AI 각색" | "추정", "source_ids": ["sillok-001"]}
```

본 모듈은 이 블록을 파싱해 (badge, source_ids, body_text)로 분리한다.
스트리밍 중간 상태에서도 사용자가 raw JSON을 보지 않도록 sanitizer를 함께 제공한다.
"""
from __future__ import annotations

import json
import re
from typing import Tuple


# 완전한 코드블록
BADGE_BLOCK_RE = re.compile(r"```badge\s*\n(.*?)\n```\s*\n?", re.DOTALL)
# 코드블록 없이 인라인 JSON으로만 응답한 경우의 폴백
BADGE_INLINE_RE = re.compile(
    r"^\s*\{[^{}]*\"badge\"[^{}]*\}\s*", re.MULTILINE
)
# 스트리밍 도중 아직 닫히지 않은 코드블록
BADGE_BLOCK_PARTIAL_RE = re.compile(r"```badge[\s\S]*$", re.DOTALL)
# 스트리밍 도중 아직 완성되지 않은 인라인 JSON (응답 맨 앞)
BADGE_INLINE_PARTIAL_RE = re.compile(r"^\s*\{[^}]*$")


VALID_BADGES = {"사료 확인됨", "AI 각색", "추정"}

# 게임 UI 톤에 맞춘 부드러운 파스텔 — 검은 잉크 테두리와 함께 스티커처럼
BADGE_COLOR = {
    "사료 확인됨": "#B7DDA6",   # soft sage green
    "AI 각색":   "#C7D9F0",    # soft sky blue
    "추정":      "#FFD9A0",    # soft apricot
}

BADGE_FG = {
    "사료 확인됨": "#1F4D1C",
    "AI 각색":   "#1F3A5F",
    "추정":      "#7A3E0A",
}

# 이모지 fallback (SVG가 안 보일 때)
BADGE_ICON = {
    "사료 확인됨": "✨",
    "AI 각색":   "🖌",
    "추정":      "🌫",
}

# 다국어 라벨 (배지 표기는 한국어 고정이되 툴팁에서 부가 설명 가능)
BADGE_LABEL_BY_LANG = {
    "ko": {"사료 확인됨": "사료 확인됨", "AI 각색": "AI 각색", "추정": "추정"},
    "en": {"사료 확인됨": "Verified by Sillok", "AI 각색": "AI Narration", "추정": "Inferred"},
    "ja": {"사료 확인됨": "史料で確認", "AI 각색": "AIによる脚色", "추정": "推定"},
    "zh": {"사료 확인됨": "史料确认", "AI 각색": "AI演绎", "추정": "推断"},
}


def parse_response(text: str) -> Tuple[str, list[str], str]:
    """LLM 응답을 (badge, source_ids, body_text)로 분리.

    파싱 실패 시 ("추정", [], text)를 반환하여 안전한 기본값을 유지한다.
    """
    # 1) 코드블록 형식 우선
    m = BADGE_BLOCK_RE.search(text)
    if m:
        try:
            obj = json.loads(m.group(1))
            badge = obj.get("badge", "").strip()
            badge = badge if badge in VALID_BADGES else "추정"
            sids = obj.get("source_ids") or []
            source_ids = [str(s) for s in sids] if isinstance(sids, list) else []
            body = BADGE_BLOCK_RE.sub("", text, count=1).strip()
            return badge, source_ids, body
        except json.JSONDecodeError:
            pass

    # 2) 인라인 JSON 형식 폴백
    m2 = BADGE_INLINE_RE.search(text)
    if m2:
        try:
            obj = json.loads(m2.group(0))
            badge = obj.get("badge", "").strip()
            badge = badge if badge in VALID_BADGES else "추정"
            sids = obj.get("source_ids") or []
            source_ids = [str(s) for s in sids] if isinstance(sids, list) else []
            body = BADGE_INLINE_RE.sub("", text, count=1).strip()
            return badge, source_ids, body
        except json.JSONDecodeError:
            pass

    return "추정", [], text


def sanitize_streaming_text(text: str) -> str:
    """스트리밍 중 누적된 텍스트에서 배지 블록(완성/미완성)을 가린다.

    - 완성된 ```badge ... ``` 블록은 제거
    - 닫는 펜스가 아직 도착하지 않은 미완성 블록은 통째로 숨김
    - 응답 맨 앞에 인라인 JSON이 형성 중이면 그것도 숨김

    화면에는 본문 텍스트만 깔끔하게 노출되며, 스트림이 끝난 뒤
    parse_response 로 정식 파싱한다.
    """
    if not text:
        return text
    # 완성된 블록 우선 제거
    out = BADGE_BLOCK_RE.sub("", text, count=1)
    # 미완성 코드블록 숨김
    out = BADGE_BLOCK_PARTIAL_RE.sub("", out)
    # 미완성 인라인 JSON 숨김 (응답 앞 부분에 한정)
    out = BADGE_INLINE_PARTIAL_RE.sub("", out)
    # 완성된 인라인 JSON도 본문에서 분리
    out = BADGE_INLINE_RE.sub("", out)
    return out.lstrip()


def render_badge_html(badge: str, language: str = "ko") -> str:
    """배지 HTML 스니펫 — 스티커 스타일. Streamlit unsafe_allow_html=True 와 함께 사용.

    하찮 캐릭터 톤에 맞게 검은 잉크 테두리 + 작은 오프셋 그림자 + 등장 시 팝 애니메이션.
    무드 아이콘 SVG는 core.character.MOOD_ICON 에서 가져온다.
    """
    from core.character import MOOD_ICON  # 순환참조 회피를 위해 함수 내 임포트

    if badge not in VALID_BADGES:
        badge = "추정"
    bg = BADGE_COLOR[badge]
    fg = BADGE_FG[badge]
    label = BADGE_LABEL_BY_LANG.get(language, BADGE_LABEL_BY_LANG["ko"])[badge]
    icon_svg = MOOD_ICON.get(badge, "")
    return (
        f'<span class="badge-sticker" '
        f'style="background:{bg};color:{fg};" '
        f'title="{badge}">'
        f'<span class="badge-icon">{icon_svg}</span>'
        f'<span class="badge-label">{label}</span>'
        f'</span>'
    )
