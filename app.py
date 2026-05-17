"""사초(史草) AI — Streamlit 시범 데모.

- 가로형 톱바 (사이드바 제거)
- 요시타케 신스케 풍 둥글둥글 사관 캐릭터 다수 배치
- 사관 대화 + 사료 두루마리 + 사실 확인 스티커 + 다국어

실행:
    python -m streamlit run app.py
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st


def _safe_load_env(path: Path) -> None:
    """python-dotenv가 UTF-16 BOM 파일을 못 읽는 문제 회피.
    UTF-8 → UTF-8-SIG → UTF-16 (LE/BE/auto) → latin-1 순서로 시도.
    """
    if not path.exists():
        return
    for enc in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError, OSError):
            continue
        for raw in text.splitlines():
            line = raw.strip().lstrip("﻿")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
        return  # 첫 성공한 인코딩에서 종료


_safe_load_env(Path(__file__).resolve().parent / ".env")

# Streamlit Community Cloud 등 클라우드 환경에서 secrets.toml 의 키를
# 환경변수로 노출 — 코어 모듈은 그대로 os.getenv 만 본다.
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = str(st.secrets["ANTHROPIC_API_KEY"])
except Exception:
    pass

from core.llm import stream_sagwan_response
from core.rag import search_corpus, SourceCard, load_corpus
from core.badge import parse_response, render_badge_html, sanitize_streaming_text
from core.prompts import GREETING_BY_LANG, SUGGESTED_QUESTIONS_BY_LANG, UI_TEXT
from core.character import (
    LOGO_SVG, LOCK_SVG, char_img, course_thumb,
)
from core.quest import (
    generate_question, pick_card, QUEST_THEME_KEYWORDS,
    COURSES, course_card_count, pick_course_card, ending_tier,
    pick_nearest_card, pick_nearby_cards, pick_random_nearby,
)
import random as _random


st.set_page_config(
    page_title="사초 AI — 졸린 사관과 함께",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─────────────────────────────────────────────────────────────
# OG 메타 + PWA Apple touch <head> 주입 — JS 런타임 인젝션
# Streamlit Cloud 의 <head> 직접 편집 불가 → JS 가 head 에 meta/link 삽입
# 이미지는 GitHub raw 직접 호스팅 (static serving 불필요)
# 대상: Twitter/Discord/Slack/LinkedIn (JS 실행 크롤러) + iOS Safari (홈 화면)
# 한계: KakaoTalk 등 JS 미실행 크롤러는 미적용
# ─────────────────────────────────────────────────────────────
_OG_TITLE = "사초(史草) AI — 한국사 사료 검증형 퀴즈 게임"
_OG_DESC = "한국사 1차 사료 + AI 무한 출제 · 한·영·일·중 동시 지원 · 문체부 AI 공모전"
_OG_URL = "https://sacho-ai.streamlit.app"
_GH_RAW = "https://raw.githubusercontent.com/dailyweekly/sacho-ai-demo/main"
_OG_IMAGE = f"{_GH_RAW}/assets/og_share.png"
_APPLE_TOUCH = f"{_GH_RAW}/assets/icon_apple_180.png"
_THEME_COLOR = "#C97064"

st.markdown(
    f"""
    <script>
    (function() {{
        if (window._sacho_head_v2) return;
        window._sacho_head_v2 = true;
        const head = document.head;
        function setMeta(attr, name, content) {{
            let m = head.querySelector(`meta[${{attr}}="${{name}}"]`);
            if (!m) {{
                m = document.createElement('meta');
                m.setAttribute(attr, name);
                head.appendChild(m);
            }}
            m.setAttribute('content', content);
        }}
        function setLink(rel, href) {{
            let l = head.querySelector(`link[rel="${{rel}}"]`);
            if (!l) {{
                l = document.createElement('link');
                l.setAttribute('rel', rel);
                head.appendChild(l);
            }}
            l.setAttribute('href', href);
        }}
        // Open Graph
        setMeta('property', 'og:type', 'website');
        setMeta('property', 'og:title', '{_OG_TITLE}');
        setMeta('property', 'og:description', '{_OG_DESC}');
        setMeta('property', 'og:image', '{_OG_IMAGE}');
        setMeta('property', 'og:url', '{_OG_URL}');
        setMeta('property', 'og:locale', 'ko_KR');
        setMeta('property', 'og:site_name', '사초 AI');
        // Twitter card
        setMeta('name', 'twitter:card', 'summary_large_image');
        setMeta('name', 'twitter:title', '{_OG_TITLE}');
        setMeta('name', 'twitter:description', '{_OG_DESC}');
        setMeta('name', 'twitter:image', '{_OG_IMAGE}');
        // 검색엔진
        setMeta('name', 'description', '{_OG_DESC}');
        // iOS Add-to-Home-Screen
        setLink('apple-touch-icon', '{_APPLE_TOUCH}');
        setMeta('name', 'theme-color', '{_THEME_COLOR}');
        setMeta('name', 'apple-mobile-web-app-capable', 'yes');
        setMeta('name', 'apple-mobile-web-app-status-bar-style', 'default');
        setMeta('name', 'apple-mobile-web-app-title', '사초 AI');
    }})();
    </script>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────
# 스타일 — 모던 큐트 / 요시타케 풍
# ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Gowun+Batang:wght@400;700&family=Nanum+Pen+Script&family=Yeon+Sung&family=Black+Han+Sans&family=Noto+Sans+KR:wght@400;500;700&display=swap');

    :root {
        --beige:     #FBF7F2;       /* 캐릭터 배경과 동일한 베이스 베이지 */
        --beige-dk:  #F2EBD9;
        --cream:     #FBF7F2;
        --oat:       #F2EBD9;
        --paper:     #F8F0DC;
        --ink:       #3A2A1F;       /* 따뜻한 다크 브라운 (캐릭터 외곽선과 통일) */
        --ink-soft:  #6B5440;
        --red:       #C97064;
        --red-deep:  #A8554A;
        --navy:      #4A5B73;
        --mustard:   #DBB871;
        --pink:      #F2B5B5;
        --sage:      #B5C5A8;
        --sky:       #B8D4DE;
    }

    /* ── 사이드바 완전 숨김 ───────────────────────────────── */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    section[data-testid="stSidebar"] { display: none !important; }

    /* 기본 헤더/푸터 숨김 */
    header[data-testid="stHeader"] { background: transparent; height: 0; }
    #MainMenu, footer { visibility: hidden; }

    /* ── 모든 캐릭터 SVG의 기본 표시 보장 ─────────────────── */
    .hero-char svg, .hero-peek svg,
    .greeting-char svg, .suggest-char svg,
    .thinking-char svg, .footer-char svg,
    .collection-char svg, .collection-char-side svg,
    .collection-empty-char svg,
    .deco-left svg, .deco-right svg,
    .gate-chars .char-main svg, .gate-chars .char-lock svg,
    .topbar-logo .logo-svg svg {
        display: block;
        max-width: none;
        height: auto;
    }

    /* ── 전체 배경 — 캐릭터 PNG 배경과 완전 동일한 평면 베이지 ── */
    .stApp { background: #FBF7F2; }

    .main .block-container {
        max-width: 1180px;
        padding: 0.75rem 1.75rem 1.5rem 1.75rem;
        font-family: 'Noto Sans KR', sans-serif;
        color: var(--ink);
    }
    /* 세련된 섹션 구분선 */
    h5 {
        font-family: 'Gowun Batang', serif !important;
        font-size: 15px !important;
        color: var(--ink-soft) !important;
        letter-spacing: 0.3px;
        margin: 18px 0 8px 0 !important;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(58,42,31,0.10);
        font-weight: 600 !important;
    }
    /* ── 폼 위젯 톤 통일 (radio · selectbox · expander · caption) ── */
    /* 라벨 — 작은 손글씨/세리프 톤 */
    [data-testid="stWidgetLabel"] p,
    [data-testid="stRadio"] > label,
    [data-testid="stSelectbox"] > label,
    [data-testid="stTextInput"] > label {
        font-family: 'Gowun Batang', serif !important;
        font-size: 13.5px !important;
        color: var(--ink-soft) !important;
        font-weight: 600 !important;
        letter-spacing: 0.2px;
    }

    /* ── 라디오 = 도장 토글 카드 (큰 머스타드 카드형) ── */
    [data-testid="stRadio"] [role="radiogroup"] {
        gap: 12px !important;
        display: flex !important;
        flex-wrap: wrap !important;
    }
    /* 각 라디오 옵션 = 카드 */
    [data-testid="stRadio"] [role="radiogroup"] > label {
        flex: 1 1 0;
        min-width: 170px;
        display: flex !important;
        align-items: center;
        justify-content: center;
        gap: 8px;
        background: #FFFCF5 !important;
        border: 2.5px dashed var(--ink-soft) !important;
        border-radius: 16px !important;
        padding: 12px 14px !important;
        cursor: pointer;
        transition: transform 0.1s, box-shadow 0.1s, background 0.15s,
                    border-color 0.15s, border-style 0.15s !important;
        font-family: 'Gowun Batang', serif !important;
        font-size: 14.5px !important;
        font-weight: 600 !important;
        color: var(--ink) !important;
        text-align: center;
        line-height: 1.3;
        box-shadow: 0 0 0 transparent;
        /* 한국어가 단어 중간에서 끊기지 않도록 */
        word-break: keep-all !important;
        overflow-wrap: normal !important;
    }
    /* 라디오 옵션 내부 텍스트 박스도 폰트 + 줄바꿈 강제 */
    [data-testid="stRadio"] [role="radiogroup"] > label > div {
        font-family: 'Gowun Batang', serif !important;
        font-size: 14.5px !important;
        color: var(--ink) !important;
        word-break: keep-all !important;
        overflow-wrap: normal !important;
    }
    /* 좁은 컨테이너에서 한 행에 3 카드가 안 맞으면 자동 2단/1단으로 */
    @media (max-width: 720px) {
        [data-testid="stRadio"] [role="radiogroup"] > label {
            min-width: 140px;
            padding: 10px 12px !important;
            font-size: 13.5px !important;
        }
    }
    /* hover — 살짝 떠오름 + 노란 tint */
    [data-testid="stRadio"] [role="radiogroup"] > label:hover {
        background: #FFF7DA !important;
        border-color: var(--ink) !important;
        transform: translate(-1px, -1px);
        box-shadow: 2px 2px 0 var(--ink);
    }
    /* selected (input checked) — 머스타드 도장 카드 */
    [data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(135deg, #FFE7A0 0%, #FFD55A 100%) !important;
        border: 2.5px solid var(--ink) !important;
        border-style: solid !important;
        box-shadow: 3px 3px 0 var(--ink) !important;
        color: var(--ink) !important;
        font-weight: 700 !important;
        transform: translate(-1px, -1px);
    }
    [data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) > div {
        font-weight: 700 !important;
    }
    /* 기본 라디오 동그라미 마커 숨김 — 카드 전체가 토글 역할 */
    [data-testid="stRadio"] [role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    /* selected 카드에 작은 ✓ 표시 (가상 요소) */
    [data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked)::after {
        content: '✓';
        position: absolute;
        top: -8px; right: -8px;
        width: 22px; height: 22px;
        background: var(--ink);
        color: #FFF;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 13px; font-weight: 700;
        box-shadow: 1px 1px 0 var(--mustard);
    }
    [data-testid="stRadio"] [role="radiogroup"] > label {
        position: relative;
    }

    /* 셀렉트박스 — 크림 카드 + 도장 그림자 */
    [data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background: #FBF7F2 !important;
        border: 2px solid var(--ink) !important;
        border-radius: 12px !important;
        box-shadow: 2px 2px 0 var(--ink) !important;
        font-family: 'Gowun Batang', serif !important;
        font-size: 14.5px !important;
        color: var(--ink) !important;
        min-height: 40px !important;
        transition: transform 0.08s;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"]:hover > div {
        transform: translate(-1px, -1px);
        box-shadow: 3px 3px 0 var(--ink) !important;
        background: #FFFCF0 !important;
    }
    /* 셀렉트 드롭다운 메뉴 옵션 */
    [data-baseweb="popover"] [role="listbox"] li {
        font-family: 'Gowun Batang', serif !important;
        font-size: 14px !important;
    }
    [data-baseweb="popover"] [role="listbox"] li:hover {
        background: rgba(219,184,113,0.20) !important;
    }

    /* expander — 점선 카드 + 손글씨 헤더 */
    [data-testid="stExpander"] {
        border: 2px dashed var(--ink-soft) !important;
        border-radius: 14px !important;
        background: #FFFCF5 !important;
        margin: 10px 0 !important;
        box-shadow: none !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] details > summary {
        font-family: 'Gowun Batang', serif !important;
        font-size: 14px !important;
        color: var(--ink) !important;
        font-weight: 600 !important;
        padding: 10px 14px !important;
    }
    [data-testid="stExpander"] summary:hover {
        background: rgba(219,184,113,0.10) !important;
    }
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] {
        font-family: 'Gowun Batang', serif !important;
        font-size: 13.5px !important;
    }

    /* st.caption — 손글씨 + 자그마한 흙색 */
    [data-testid="stCaptionContainer"],
    .stCaption,
    [data-testid="stMarkdownContainer"] small {
        font-family: 'Nanum Pen Script', cursive !important;
        font-size: 16px !important;
        color: var(--ink-soft) !important;
        opacity: 0.9 !important;
    }

    /* 시작 버튼 ("새 문제 받기" 등 primary action) — 강조 */
    .stButton > button:has(span:has-text("새 문제")),
    .stButton > button:has(span:has-text("시작")) {
        background: var(--mustard) !important;
    }
    /* 모든 버튼에 적용된 기본 — 만약 새 문제 버튼이 식별 안 되면 일반적으로 강조 */
    .stButton > button p {
        font-family: 'Gowun Batang', serif !important;
        font-weight: 700 !important;
    }
    h1, h2, h3, h4 {
        font-family: 'Gowun Batang', 'Gowun Dodum', serif;
        color: var(--ink);
        letter-spacing: -0.3px;
    }

    /* ── 가로형 톱바 (컴팩트·세련) ─────────────────────────── */
    .topbar {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 16px;
        background: #FBF7F2;
        border: 2px solid var(--ink);
        border-radius: 18px;
        box-shadow: 3px 3px 0 var(--ink);
        margin: 2px 0 18px 0;
        position: relative;
        backdrop-filter: blur(6px);
    }
    /* 밑줄 완전 제거 — 모든 자식 요소에 강제 적용 */
    .topbar-logo-link,
    .topbar-logo-link:link,
    .topbar-logo-link:visited,
    .topbar-logo-link:hover,
    .topbar-logo-link:active,
    .topbar-logo-link *,
    .topbar-logo-link *:hover {
        text-decoration: none !important;
        border-bottom: none !important;
        color: var(--ink) !important;
    }
    .topbar-logo-link {
        display: inline-block;
        border-radius: 14px;
        padding: 4px 8px;
        transition: transform 0.12s, background 0.15s;
        cursor: pointer;
    }
    .topbar-logo-link:hover {
        background: rgba(255, 231, 160, 0.45);
        transform: translateY(-1px);
    }
    .topbar-logo-link:active { transform: translateY(1px); }
    .topbar-logo {
        display: flex; align-items: center; gap: 12px;
        flex: 1; min-width: 0;
        position: relative;
    }
    .topbar-logo .logo-svg { animation: bob 4s ease-in-out infinite; }
    /* 텍스트 wrapper — peek 캐릭터 절대 위치 기준 */
    .topbar-logo .topbar-text-wrap {
        display: flex; flex-direction: column;
        flex: 1; min-width: 0;
    }
    /* 빼꼼 캐릭터 — 로고 우측에서 살짝 고개 내미는 듯 */
    .topbar-logo .topbar-peek {
        flex: 0 0 42px;
        animation: peek-wobble 6s ease-in-out infinite;
        margin-left: 4px;
        opacity: 0.92;
        pointer-events: none;
    }
    .topbar-logo .topbar-peek img,
    .topbar-logo .topbar-peek svg {
        width: 42px !important; height: 42px !important;
        display: block;
    }
    @keyframes peek-wobble {
        0%, 92%, 100% { transform: translateY(2px) rotate(-3deg); }
        93%, 96% { transform: translateY(-2px) rotate(8deg); }  /* 잠시 깨꼼 */
    }
    @media (max-width: 720px) {
        .topbar-logo .topbar-peek { display: none; }
    }
    @keyframes bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
    .topbar-logo .brand {
        font-family: 'Yeon Sung', 'Black Han Sans', 'Gowun Batang', serif;
        font-weight: 400;
        font-size: 30px;
        line-height: 1.05;
        color: var(--ink) !important;
        letter-spacing: 1px;
    }
    .topbar-logo .brand-sub {
        font-family: 'Nanum Pen Script', cursive;
        font-size: 15px;
        color: var(--ink-soft) !important;
        opacity: 0.8;
        margin-top: 2px;
    }

    /* 톱바 안 selectbox·버튼 컴팩트화 */
    .topbar-tools [data-baseweb="select"] > div {
        border-radius: 12px !important;
        border: 2px solid var(--ink) !important;
        background: var(--cream) !important;
        box-shadow: 2px 2px 0 var(--ink);
        min-height: 38px;
        font-family: 'Gowun Batang', serif;
    }
    .topbar-tools [data-testid="stPopover"] button,
    .topbar-tools .stButton button,
    .topbar-tools .stDownloadButton button {
        border-radius: 12px !important;
        border: 2px solid var(--ink) !important;
        background: var(--cream) !important;
        color: var(--ink) !important;
        font-family: 'Gowun Batang', serif !important;
        box-shadow: 2px 2px 0 var(--ink) !important;
        height: 38px !important;
        min-height: 38px !important;
        padding: 0 12px !important;
        font-size: 14px !important;
    }
    .topbar-tools .stButton button:hover,
    .topbar-tools .stDownloadButton button:hover {
        background: #FFF3CF !important;
        transform: translate(-1px, -1px) !important;
        box-shadow: 3px 3px 0 var(--ink) !important;
    }
    .topbar-tools .stButton button:active,
    .topbar-tools .stDownloadButton button:active {
        transform: translate(1px, 1px) !important;
        box-shadow: 0 0 0 var(--ink) !important;
    }

    /* ── 헤더 + 메인 캐릭터 큰 컷 ─────────────────────────── */
    .hero {
        display: flex; align-items: center; gap: 24px;
        background: #FBF7F2;          /* 캐릭터 PNG 배경과 동일 */
        border: 2.5px solid var(--ink);
        border-radius: 28px;
        padding: 22px 28px;
        margin-bottom: 22px;
        box-shadow: 5px 5px 0 var(--ink);
        position: relative;
        overflow: hidden;
    }
    .hero::after {
        content: ''; position: absolute; inset: 8px;
        border: 1.5px dashed rgba(42, 31, 24, 0.22);
        border-radius: 22px; pointer-events: none;
    }
    .hero-char { flex: 0 0 150px; animation: float-y 5s ease-in-out infinite; }
    @keyframes float-y { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
    .hero-text { flex: 1; }
    .hero-text h1 {
        margin: 0; font-size: 30px; font-weight: 700;
    }
    .hero-text p {
        margin: 8px 0 0 0;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 20px; line-height: 1.45; color: var(--ink-soft);
    }
    /* ── 퀘스트 랜딩 hero banner (문제 시작 전만) ── */
    .quest-hero-banner {
        width: 100%;
        max-height: 240px;
        overflow: hidden;
        border-radius: 16px;
        border: 2px solid var(--ink);
        box-shadow: 3px 3px 0 var(--ink);
        margin: 0 0 14px 0;
        animation: hero-banner-in 0.7s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .quest-hero-banner img {
        display: block;
        width: 100%; height: auto;
    }
    @media (max-width: 720px) {
        .quest-hero-banner { max-height: 160px; border-radius: 12px; }
    }
    @media (max-width: 420px) {
        .quest-hero-banner { max-height: 120px; }
    }

    /* ── Hero scene mode (사용자 제공 wide banner 일러스트) ── */
    .hero.hero-scene-mode {
        flex-direction: column;
        align-items: stretch;
        padding: 14px;
        gap: 14px;
        background: linear-gradient(180deg, #FBF7F2 0%, #FFF1D6 100%);
    }
    .hero.hero-scene-mode::after {
        inset: 6px;
        border-radius: 22px;
    }
    .hero-banner {
        width: 100%;
        max-height: 280px;
        overflow: hidden;
        border-radius: 18px;
        border: 2px solid var(--ink);
        box-shadow: 3px 3px 0 var(--ink);
        position: relative;
        animation: hero-banner-in 0.7s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .hero-banner img {
        display: block;
        width: 100%; height: auto;
    }
    @keyframes hero-banner-in {
        0% { opacity: 0; transform: translateY(-8px) scale(0.99); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    .hero.hero-scene-mode .hero-text {
        text-align: center;
        padding: 4px 14px 8px 14px;
    }
    .hero.hero-scene-mode .hero-text h1 {
        font-family: 'Yeon Sung', 'Black Han Sans', serif;
        font-size: 28px;
        color: var(--ink);
        letter-spacing: 0.5px;
    }
    .hero.hero-scene-mode .hero-text p {
        max-width: 720px;
        margin: 8px auto 0 auto;
    }
    /* scene mode 에선 hero-peek 사용 안 함 */
    .hero.hero-scene-mode .hero-peek { display: none; }
    @media (max-width: 720px) {
        .hero.hero-scene-mode { padding: 10px; gap: 10px; }
        .hero-banner { max-height: 180px; border-radius: 14px; }
        .hero.hero-scene-mode .hero-text h1 { font-size: 22px; }
        .hero.hero-scene-mode .hero-text p { font-size: 17px; }
    }
    @media (max-width: 420px) {
        .hero-banner { max-height: 140px; }
    }

    /* hero 우측 빼꼼 캐릭터 */
    .hero-peek {
        position: absolute; right: -10px; bottom: -2px;
        transform: rotate(-6deg); opacity: 0.85;
        pointer-events: none;
        animation: peek-wobble 6s ease-in-out infinite;
    }
    @keyframes peek-wobble {
        0%, 100% { transform: rotate(-6deg) translateY(0); }
        50% { transform: rotate(-2deg) translateY(-4px); }
    }

    /* ── 빈 화면 인사 카드 ───────────────────────────────── */
    .greeting-card {
        display: flex; gap: 18px; align-items: flex-start;
        background: var(--cream);
        border: 2.5px solid var(--ink);
        border-radius: 24px;
        padding: 18px 22px;
        box-shadow: 4px 4px 0 var(--ink);
        margin: 12px 0 22px 0;
        position: relative;
    }
    .greeting-char { flex: 0 0 110px; animation: wobble 6s ease-in-out infinite; }
    @keyframes wobble {
        0%, 100% { transform: rotate(-2.5deg); }
        50% { transform: rotate(2.5deg); }
    }
    .greeting-bubble {
        background: #FFF;
        border: 2px solid var(--ink);
        border-radius: 18px;
        padding: 14px 18px;
        font-family: 'Gowun Batang', serif;
        font-size: 16px; line-height: 1.7;
        flex: 1; position: relative;
    }
    .greeting-bubble::before {
        content: ''; position: absolute;
        left: -10px; top: 30px;
        width: 0; height: 0;
        border-top: 9px solid transparent;
        border-bottom: 9px solid transparent;
        border-right: 12px solid var(--ink);
    }
    .greeting-bubble::after {
        content: ''; position: absolute;
        left: -7px; top: 31px;
        width: 0; height: 0;
        border-top: 8px solid transparent;
        border-bottom: 8px solid transparent;
        border-right: 11px solid #FFF;
    }

    /* ── 🎮 퀘스트 게임 페이지 ───────────────────────────── */
    /* 사초·연승·정답률 띠 */
    .credit-bar {
        display: flex; flex-wrap: wrap; gap: 18px;
        background: #FFF7DA;
        border: 2px solid var(--ink);
        border-radius: 14px;
        padding: 10px 18px;
        margin-bottom: 16px;
        font-family: 'Gowun Batang', serif;
        font-size: 14.5px;
    }
    .credit-bar b { color: var(--red-deep); font-weight: 700; }
    .credit-bar .credit-num {
        font-family: 'Yeon Sung', serif;
        font-size: 18px;
        color: var(--ink);
        margin-left: 4px;
        display: inline-block;
        /* 매 render 마다 살짝 pop — 변경된 값임을 시각적으로 확인 */
        animation: credit-pop 0.7s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    @keyframes credit-pop {
        0% { transform: scale(1.5); color: var(--mustard); }
        60% { transform: scale(0.95); }
        100% { transform: scale(1); color: var(--ink); }
    }
    .credit-bar .credit-best {
        font-family: 'Nanum Pen Script', cursive;
        color: var(--ink-soft); font-size: 14px;
    }

    /* 퀘스트 인트로 (문제 없을 때) */
    .quest-intro {
        display: flex; gap: 18px; align-items: center;
        background: #FBF7F2;
        border: 2.5px solid var(--ink);
        border-radius: 22px;
        padding: 18px 22px;
        margin-bottom: 14px;
        box-shadow: 4px 4px 0 var(--ink);
    }
    .quest-intro-char { flex: 0 0 110px; animation: float-y 5s ease-in-out infinite; }
    .quest-intro-text h3 {
        margin: 0; font-family: 'Yeon Sung', serif; font-size: 22px;
    }
    .quest-intro-text p {
        margin: 4px 0 0 0; font-family: 'Gowun Batang', serif;
        font-size: 14.5px; color: var(--ink); line-height: 1.6;
    }

    /* 문제 카드 — 등장 시 slide-down 애니메이션 */
    .quest-q {
        display: flex; gap: 14px; align-items: flex-start;
        background: #FFFCF0;
        border: 2.5px solid var(--ink);
        border-radius: 18px;
        padding: 18px 20px;
        margin-bottom: 14px;
        box-shadow: 4px 4px 0 var(--ink);
        animation: quest-slide-in 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    @keyframes quest-slide-in {
        0% { opacity: 0; transform: translateY(-12px) scale(0.98); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    .quest-q-tag {
        flex: 0 0 38px; height: 38px; line-height: 36px;
        text-align: center;
        background: var(--mustard);
        border: 2px solid var(--ink);
        border-radius: 10px;
        font-family: 'Yeon Sung', serif;
        font-size: 22px;
        box-shadow: 2px 2px 0 var(--ink);
        /* Q. 태그 — 새 문제 시 살짝 흔들리며 시선 끌기 */
        animation: q-tag-pop 0.7s ease-out;
    }
    @keyframes q-tag-pop {
        0% { transform: scale(0) rotate(-180deg); }
        60% { transform: scale(1.2) rotate(10deg); }
        100% { transform: scale(1) rotate(0deg); }
    }
    .quest-q-body {
        flex: 1;
        font-family: 'Gowun Batang', serif;
        font-size: 17px;
        line-height: 1.7;
        color: var(--ink);
    }

    /* 결과 띠 (구) */
    .quest-result {
        padding: 12px 16px;
        border-radius: 12px;
        font-family: 'Gowun Batang', serif;
        font-weight: 700;
        font-size: 15.5px;
        margin: 12px 0;
        border: 2px solid var(--ink);
        box-shadow: 2px 2px 0 var(--ink);
    }
    .quest-result.correct {
        background: #DDF0CB;
        color: #2E6418;
    }
    .quest-result.wrong {
        background: #FFE0D6;
        color: #8C2A18;
    }
    /* 결과 패널 (NEW) — 캐릭터 + 멘트 + 시간 */
    .quest-result-panel {
        display: flex; gap: 16px; align-items: center;
        border: 2.5px solid var(--ink);
        border-radius: 16px;
        padding: 14px 18px;
        margin: 14px 0;
        box-shadow: 3px 3px 0 var(--ink);
    }
    .quest-result-panel.correct {
        background: linear-gradient(135deg, #E8F4D8 0%, #C8E0AC 100%);
    }
    .quest-result-panel.wrong {
        background: linear-gradient(135deg, #FFE8DC 0%, #FFCFB6 100%);
    }
    .quest-result-panel .qr-char {
        flex: 0 0 100px;
        animation: result-bob 1.2s ease-in-out infinite;
    }
    .quest-result-panel.correct .qr-char { animation-name: result-jump; }
    @keyframes result-bob {
        0%, 100% { transform: rotate(-3deg); }
        50% { transform: rotate(3deg); }
    }
    @keyframes result-jump {
        0%, 100% { transform: translateY(0); }
        30% { transform: translateY(-8px); }
        60% { transform: translateY(0); }
    }
    .quest-result-panel .qr-body { flex: 1; }
    .quest-result-panel .qr-label {
        font-family: 'Yeon Sung', 'Black Han Sans', serif;
        font-size: 19px;
        margin-bottom: 6px;
    }
    .quest-result-panel.correct .qr-label { color: #1E4D0F; }
    .quest-result-panel.wrong   .qr-label { color: #7A1F0F; }
    .quest-result-panel .qr-taunt {
        font-family: 'Gowun Batang', serif;
        font-size: 14.5px;
        font-style: italic;
        color: var(--ink);
        margin-bottom: 6px;
    }
    .quest-result-panel .qr-time {
        font-family: 'Nanum Pen Script', cursive;
        font-size: 17px;
        color: var(--ink-soft);
    }
    /* 정답 시 결과 패널 주변에 ✨ 파티클 폭발 (귀여움 + 장난) */
    .quest-result-panel.correct {
        position: relative;
    }
    .quest-result-panel.correct::before,
    .quest-result-panel.correct::after {
        content: '✨ ✦ ✨ ✦ ✨ ✦ ✨';
        position: absolute;
        left: 0; right: 0;
        text-align: center;
        font-size: 18px;
        letter-spacing: 14px;
        color: #DBB871;
        pointer-events: none;
        animation: sparkle-burst 1.8s ease-out;
    }
    .quest-result-panel.correct::before {
        top: -22px;
        animation-delay: 0s;
    }
    .quest-result-panel.correct::after {
        bottom: -22px;
        animation-delay: 0.3s;
        font-size: 14px;
        color: #C97064;
    }
    @keyframes sparkle-burst {
        0% { opacity: 0; transform: scale(0.4); letter-spacing: 4px; }
        50% { opacity: 1; transform: scale(1.1); letter-spacing: 16px; }
        100% { opacity: 0.5; transform: scale(1); letter-spacing: 14px; }
    }
    /* 오답도 살짝 — 비 내리듯 ☔ 작게 */
    .quest-result-panel.wrong::before {
        content: '☔ · ☔ · ☔';
        position: absolute;
        top: -18px; left: 0; right: 0;
        text-align: center;
        font-size: 13px;
        letter-spacing: 24px;
        color: rgba(122, 31, 15, 0.4);
        pointer-events: none;
        animation: drizzle 1.5s ease-out;
    }
    @keyframes drizzle {
        0% { opacity: 0; transform: translateY(-6px); }
        100% { opacity: 0.6; transform: translateY(0); }
    }
    /* 모바일: 결과 패널 세로 + 캐릭터 축소 */
    @media (max-width: 720px) {
        .quest-result-panel {
            flex-direction: column; align-items: center;
            text-align: center;
            padding: 12px 14px;
            gap: 8px;
        }
        .quest-result-panel .qr-char { flex: 0 0 70px; }
        .quest-result-panel .qr-char svg { width: 70px !important; height: 70px !important; }
        .quest-result-panel .qr-label { font-size: 17px; }
        .quest-result-panel .qr-taunt { font-size: 13.5px; }
        .quest-result-panel .qr-time { font-size: 15px; }
    }

    /* 답변 후 선지 회고 */
    .opt-recap {
        background: #FBF7F2;
        border: 1.5px dashed rgba(58,42,31,0.22);
        border-radius: 12px;
        padding: 10px 14px;
        margin-bottom: 14px;
        font-family: 'Gowun Batang', serif;
    }
    .opt-recap .opt-row {
        padding: 4px 6px;
        font-size: 14px;
        color: var(--ink-soft);
    }
    .opt-recap .opt-row.opt-correct {
        color: #2E6418; font-weight: 700;
        background: rgba(181,197,168,0.30);
        border-left: 3px solid #2E6418;
        padding-left: 10px;
    }
    .opt-recap .opt-row.opt-wrong {
        color: #8C2A18;
        background: rgba(201,112,100,0.20);
        border-left: 3px solid #8C2A18;
        padding-left: 10px;
        text-decoration: line-through;
    }

    /* 랜딩 지도 헤더 + 범례 */
    .landing-map-head {
        display: flex; align-items: center; justify-content: space-between;
        gap: 12px; flex-wrap: wrap;
        margin: 0 0 8px 0;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(58,42,31,0.10);
    }
    .landing-map-sub {
        font-family: 'Nanum Pen Script', cursive;
        font-size: 15px;
        color: var(--ink-soft);
        opacity: 0.85;
    }
    .landing-map-geo {
        display: inline-flex; align-items: center;
        background: #FFF7DA;
        border: 1.5px dashed #C97064;
        border-radius: 999px;
        padding: 4px 12px;
        font-family: 'Gowun Batang', serif;
        font-size: 12px;
        color: var(--ink);
    }
    .landing-map-geo .geo-status b { color: #2E6418; }
    .geo-hint {
        display: flex; align-items: center; height: 36px;
        font-family: 'Gowun Batang', serif;
        font-size: 13px;
        color: var(--ink-soft);
        background: #FFFCEF;
        border: 1.5px dashed rgba(58,42,31,0.20);
        border-radius: 10px;
        padding: 0 14px;
        margin: -4px 0 8px 0;
    }
    /* ── 키보드 단축키 힌트 (질문 중) ── */
    .kbd-hint-row {
        text-align: center;
        margin: 4px 0 10px 0;
        font-family: 'Gowun Batang', serif;
        font-size: 11.5px;
        color: var(--ink-soft);
        opacity: 0.85;
    }
    .kbd-hint-row .kbd-key {
        display: inline-block;
        min-width: 20px;
        padding: 1px 6px;
        margin: 0 2px;
        background: #FFFCEF;
        border: 1.5px solid var(--ink-soft);
        border-bottom-width: 2.5px;
        border-radius: 5px;
        font-family: 'Yeon Sung', monospace;
        font-size: 11.5px;
        font-weight: 700;
        color: var(--ink);
        line-height: 1.2;
        text-align: center;
    }
    @media (max-width: 720px) {
        .kbd-hint-row { display: none; }  /* 모바일 키보드 없으니 숨김 */
    }

    /* ── K-콘텐츠 모드 페르소나 인트로 ── */
    .kculture-intro {
        display: flex; gap: 12px; align-items: center;
        background: linear-gradient(135deg, #FFF0F5 0%, #FFE0E8 100%);
        border: 2px dashed #C97064;
        border-radius: 14px;
        padding: 12px 16px;
        margin: 8px 0 12px 0;
        box-shadow: 2px 2px 0 rgba(201, 112, 100, 0.30);
    }
    .kculture-intro .kculture-intro-char {
        flex: 0 0 72px;
        animation: float-y 4s ease-in-out infinite;
    }
    /* 전용 일러스트 모드 — hmm 폴백보다 큼 (120px) + 입체 그림자 */
    .kculture-intro .kculture-intro-char.kc-illust {
        flex: 0 0 120px;
    }
    .kculture-intro .kculture-intro-char.kc-illust img {
        max-width: 100%; height: auto;
        border-radius: 12px;
        filter: drop-shadow(0 2px 4px rgba(58, 42, 31, 0.12));
    }
    .kculture-intro .kculture-intro-text {
        flex: 1;
        font-family: 'Gowun Batang', serif;
        font-size: 13.5px;
        line-height: 1.6;
        color: var(--ink);
    }
    .kculture-intro .kc-tag {
        display: inline-block;
        background: #C97064;
        color: #FFF;
        padding: 2px 10px;
        border-radius: 999px;
        font-family: 'Yeon Sung', serif;
        font-size: 12px;
        letter-spacing: 1px;
        margin-bottom: 4px;
    }
    .kculture-intro b { color: #6A1F18; }
    .kculture-intro small { color: var(--ink-soft); opacity: 0.85; }
    @media (max-width: 720px) {
        .kculture-intro { flex-direction: column; text-align: center; }
        /* hmm 폴백 — 작게 */
        .kculture-intro .kculture-intro-char svg,
        .kculture-intro .kculture-intro-char:not(.kc-illust) img {
            width: 56px !important; height: 56px !important;
        }
        /* kc-illust 전용 일러스트 — hero 처럼 풀너비 60% */
        .kculture-intro .kculture-intro-char.kc-illust {
            flex: 0 0 auto;
            width: 60%; max-width: 200px;
            align-self: center;
        }
        .kculture-intro .kculture-intro-char.kc-illust img {
            width: 100% !important; height: auto !important;
        }
    }

    /* ── 시간 보너스 인라인 힌트 (질문 중 시간 압박감) ── */
    .time-hint-row {
        display: flex; flex-wrap: wrap; gap: 6px;
        justify-content: center;
        margin: -2px 0 10px 0;
    }
    .time-hint-pill {
        display: inline-flex; align-items: center; gap: 4px;
        font-family: 'Gowun Batang', serif;
        font-size: 11.5px;
        padding: 3px 10px;
        border-radius: 999px;
        border: 1px dashed;
        color: var(--ink);
        background: #FFFCEF;
    }
    .time-hint-pill b { font-weight: 800; }
    .time-hint-pill.bonus   { border-color: #2E6418; color: #2E6418; background: #EAF5DF; }
    .time-hint-pill.neutral { border-color: #6B5A40; }
    .time-hint-pill.penalty { border-color: #C97064; color: #8C2A18; background: #FFEDE3; }
    .time-hint-pill.bad     { border-color: #6A1F18; color: #6A1F18; background: #FFE3D6; }
    @media (max-width: 720px) {
        .time-hint-pill { font-size: 10.5px; padding: 2px 8px; }
    }

    /* 결과 패널 우측의 "빠른 다음" 버튼 — outline 스타일 */
    [data-testid="stButton"] button[kind="secondary"]:has(div:contains("⏭")),
    button[kind="secondary"]:has(div:contains("⏭")) {
        /* :has 미지원 폴백 — Streamlit 키 기반 직접 셀렉터로 덮음 */
    }
    button[data-testid="baseButton-secondary"][aria-label*="quest_next_quick"],
    [data-testid="stButton"] button[key="quest_next_quick"] {
        background: #FFFCEF !important;
        border: 2px dashed var(--ink-soft) !important;
        color: var(--ink) !important;
        font-size: 13px !important;
        padding: 6px 10px !important;
        min-height: 32px !important;
        box-shadow: none !important;
        font-family: 'Gowun Batang', serif !important;
        font-weight: 600 !important;
    }
    button[data-testid="baseButton-secondary"][aria-label*="quest_next_quick"]:hover,
    [data-testid="stButton"] button[key="quest_next_quick"]:hover {
        background: #FFE9A6 !important;
        border-color: var(--ink) !important;
    }

    /* 랜딩 지도 접힘 안내 바 */
    .landing-map-collapsed-hint {
        background: #FFFCEF;
        border: 1.5px dashed rgba(58,42,31,0.30);
        border-radius: 10px;
        padding: 10px 16px;
        margin: 4px 0 10px 0;
        font-family: 'Gowun Batang', serif;
        font-size: 13px;
        color: var(--ink-soft);
        text-align: center;
    }
    /* Folium iframe 모바일 압축 */
    @media (max-width: 720px) {
        .landing-map-folium iframe { height: 260px !important; }
        .landing-map-folium.expanded iframe { height: 480px !important; }
    }
    /* 크게 보기 모드 — 강조 테두리 + 약한 그림자로 "전체 화면 느낌" */
    .landing-map-folium.expanded {
        border: 2.5px solid var(--ink);
        border-radius: 14px;
        box-shadow: 4px 4px 0 var(--ink), 0 8px 18px rgba(58,42,31,0.10);
        overflow: hidden;
        margin: 4px 0 14px 0;
    }
    .landing-map-folium.expanded iframe {
        border-radius: 12px;
    }
    /* ── API 키 누락 경고 (랜딩 최상단) ── */
    .api-key-warn {
        background: linear-gradient(135deg, #FFE3D6, #FFD0BB);
        border: 2px solid #C97064;
        border-radius: 12px;
        padding: 10px 16px;
        margin: 0 0 12px 0;
        font-family: 'Gowun Batang', serif;
        font-size: 13.5px;
        color: #6A1F18;
        box-shadow: 2px 2px 0 rgba(58,42,31,0.15);
    }
    .api-key-warn small { opacity: 0.7; }

    /* ── 처음 사용자 onboarding 카드 ── */
    .onboarding-card {
        background: linear-gradient(135deg, #FFFCF0 0%, #FFF6D6 100%);
        border: 2.5px solid var(--ink);
        border-radius: 16px;
        padding: 14px 18px 12px 18px;
        margin: 0 0 14px 0;
        box-shadow: 3px 3px 0 var(--ink);
    }
    .onboarding-card .onb-head {
        display: flex; align-items: center; gap: 10px;
        margin-bottom: 10px;
    }
    .onboarding-card .onb-badge {
        background: var(--mustard);
        color: var(--ink);
        border: 2px solid var(--ink);
        border-radius: 999px;
        padding: 2px 10px;
        font-family: 'Yeon Sung', serif;
        font-size: 13px;
        letter-spacing: 1px;
        box-shadow: 1.5px 1.5px 0 var(--ink);
    }
    .onboarding-card .onb-head h4 {
        margin: 0; border: none;
        font-family: 'Gowun Batang', serif;
        font-size: 16px; color: var(--ink);
    }
    .onboarding-card .onb-grid {
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 10px; margin-bottom: 10px;
    }
    .onboarding-card .onb-cell {
        background: #FFFDF6;
        border: 1.5px dashed rgba(58,42,31,0.30);
        border-radius: 10px;
        padding: 10px 12px;
        font-family: 'Gowun Batang', serif;
    }
    .onboarding-card .onb-cell .onb-icon { font-size: 22px; margin-bottom: 2px; }
    .onboarding-card .onb-cell b { font-size: 14px; color: var(--red-deep); }
    .onboarding-card .onb-cell p {
        margin: 4px 0 0 0;
        font-size: 12px; line-height: 1.5;
        color: var(--ink);
    }
    .onboarding-card .onb-rec {
        background: #FFF7DA;
        border-left: 4px solid var(--mustard);
        border-radius: 4px 10px 10px 4px;
        padding: 8px 14px;
        font-family: 'Gowun Batang', serif;
        font-size: 13px;
        color: var(--ink);
    }
    @media (max-width: 720px) {
        .onboarding-card .onb-grid { grid-template-columns: 1fr; }
        .landing-map-head { flex-direction: column; align-items: flex-start; }
    }
    .map-legend {
        display: flex; flex-wrap: wrap; gap: 10px 18px;
        background: #FBF7F2;
        border: 1.5px dashed var(--ink-soft);
        border-radius: 10px;
        padding: 8px 14px;
        margin: 8px 0 14px 0;
        font-family: 'Gowun Batang', serif;
        font-size: 13px;
        color: var(--ink);
    }
    .map-legend span b {
        font-size: 15px; margin-right: 4px;
    }

    /* 권역 라벨 (코스 선택 직후) — 손글씨 + 핀 */
    .area-tag {
        display: inline-block;
        margin-top: 6px;
        padding: 4px 14px;
        background: #FFF7DA;
        border: 1.5px dashed var(--mustard);
        border-radius: 999px;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 16.5px;
        color: var(--ink-soft);
    }

    /* '새 문제 받기' primary 시작 버튼 강조 */
    .start-btn-wrap button {
        background: linear-gradient(135deg, #FFE7A0 0%, #FFD55A 100%) !important;
        border: 2.5px solid var(--ink) !important;
        box-shadow: 4px 4px 0 var(--ink) !important;
        font-size: 16px !important;
        padding: 14px 18px !important;
        min-height: 64px !important;
        font-family: 'Yeon Sung', 'Gowun Batang', serif !important;
        letter-spacing: 0.5px;
    }
    .start-btn-wrap button:hover {
        background: linear-gradient(135deg, #FFD55A 0%, #FFC640 100%) !important;
        transform: translate(-2px, -2px) !important;
        box-shadow: 6px 6px 0 var(--ink) !important;
    }
    .start-btn-wrap button:active {
        transform: translate(2px, 2px) !important;
        box-shadow: 1px 1px 0 var(--ink) !important;
    }

    /* nearby 모드 안내 박스 */
    .nearby-hint {
        background: #FFF7DA;
        border: 1.5px dashed var(--ink-soft);
        border-radius: 12px;
        padding: 10px 14px;
        margin: 8px 0 12px 0;
        font-family: 'Gowun Batang', serif;
        font-size: 13.5px;
        color: var(--ink);
    }
    /* 3단계 트리거 알림 (현장·도보·당일) */
    .nearby-tier {
        background: linear-gradient(135deg, #FFFCF5 0%, #FFF6E0 100%);
        border: 2px solid var(--ink);
        border-left: 6px solid var(--mustard);
        border-radius: 10px;
        padding: 12px 16px;
        margin: 10px 0;
        font-family: 'Gowun Batang', serif;
        font-size: 14.5px;
        color: var(--ink);
        box-shadow: 2px 2px 0 var(--ink);
    }
    .nearby-tier b { color: var(--red-deep); }
    /* 직접 골라서 — 리스트 헤더 */
    .nearby-list-head {
        margin: 14px 0 8px 0;
        font-family: 'Gowun Batang', serif;
        font-size: 14px; font-weight: 600;
        color: var(--ink);
    }
    .nearby-list-head small {
        font-family: 'Nanum Pen Script', cursive;
        font-size: 14px;
        color: var(--ink-soft);
    }
    /* 근처 사료 한 줄 — 카드 */
    .nearby-row {
        background: #FBF7F2;
        border: 1.5px solid rgba(58,42,31,0.18);
        border-radius: 12px;
        padding: 10px 14px;
        margin: 6px 0;
        font-family: 'Gowun Batang', serif;
        transition: transform 0.1s, border-color 0.1s;
    }
    .nearby-row:hover {
        transform: translate(-1px, -1px);
        border-color: var(--ink);
    }
    .nearby-row-title {
        font-size: 14.5px;
        color: var(--ink);
        margin-bottom: 4px;
    }
    .nearby-row-meta {
        font-size: 12.5px;
        color: var(--ink-soft);
    }
    .cat-pill {
        display: inline-block;
        padding: 1px 8px;
        border-radius: 999px;
        font-size: 11.5px;
        font-weight: 600;
        margin-left: 4px;
    }

    /* 코스 진행 표시 — 미니 썸네일 + 텍스트 + 시각 진행 바 */
    .course-progress {
        display: flex; gap: 12px; align-items: center;
        background: #FFF7DA;
        border: 1.5px dashed var(--ink);
        border-radius: 12px;
        padding: 10px 14px;
        font-family: 'Gowun Batang', serif;
        font-size: 13.5px;
        color: var(--ink);
        margin-bottom: 12px;
    }
    .course-progress-mini {
        flex: 0 0 52px;
        border-radius: 8px;
        overflow: hidden;
        border: 1.5px solid rgba(58,42,31,0.30);
        box-shadow: 1.5px 1.5px 0 rgba(58,42,31,0.10);
    }
    .course-progress-mini img { display: block; width: 100%; height: auto; }
    .course-progress-main { flex: 1; min-width: 0; }

    /* ── 코스 picker 후 preview 카드 (랜딩) — 일러스트 + 메타 ── */
    .course-preview {
        display: flex; gap: 14px; align-items: center;
        background: linear-gradient(135deg, #FFFCEF 0%, #FFF7DA 100%);
        border: 2.5px solid var(--ink);
        border-radius: 14px;
        padding: 12px 16px;
        margin: 8px 0 10px 0;
        box-shadow: 3px 3px 0 var(--ink);
        animation: course-preview-in 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    @keyframes course-preview-in {
        0% { opacity: 0; transform: translateY(-6px) scale(0.98); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    .course-preview-thumb {
        flex: 0 0 140px;
        border-radius: 10px;
        overflow: hidden;
        border: 2px solid var(--ink);
        box-shadow: 2px 2px 0 var(--ink);
    }
    .course-preview-thumb img { display: block; width: 100%; height: auto; }
    .course-preview-text { flex: 1; min-width: 0; }
    .course-preview-name {
        font-family: 'Yeon Sung', serif;
        font-size: 15px;
        color: var(--red-deep);
        margin-bottom: 4px;
        line-height: 1.3;
    }
    .course-preview-meta {
        font-family: 'Nanum Pen Script', cursive;
        font-size: 15px;
        color: var(--ink-soft);
        margin-bottom: 4px;
    }
    .course-preview-cards {
        font-family: 'Gowun Batang', serif;
        font-size: 12.5px;
        color: var(--ink);
    }
    .course-preview-cards b { color: var(--red-deep); }
    @media (max-width: 720px) {
        .course-preview { flex-direction: column; text-align: center; }
        .course-preview-thumb { flex: 0 0 auto; width: 70%; max-width: 220px; }
        .course-progress-mini { flex: 0 0 44px; }
    }
    .course-progress b { color: var(--red-deep); }
    /* 진행 단계 점(dot) 시리즈 — ●●●○○○○ 식 시각화 */
    .course-progress-bar {
        display: flex; gap: 6px; align-items: center;
        margin-top: 8px;
        flex-wrap: wrap;
    }
    .course-progress-step {
        flex: 1 1 12px; min-width: 12px;
        height: 10px;
        border-radius: 6px;
        border: 1.5px solid var(--ink);
        background: #FFFCEF;
        transition: all 0.2s;
    }
    .course-progress-step.done {
        background: #2E6418;
        box-shadow: inset 0 0 0 1.5px rgba(255,255,255,0.25);
    }
    .course-progress-step.current {
        background: var(--mustard);
        animation: step-pulse 1.4s ease-in-out infinite;
        box-shadow: 0 0 0 2px rgba(219, 184, 113, 0.35);
    }
    @keyframes step-pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.15); }
    }
    .course-progress-meter {
        display: inline-flex; gap: 6px; align-items: baseline;
        margin-left: 6px;
        font-family: 'Yeon Sung', serif;
        font-size: 15px;
        color: var(--red-deep);
    }

    /* ── 힌트 버튼 — 답안 stamp 보다 BEFORE 정의 (cascade 순서 중요)
     * answer-stamp 가 hint-reset 보다 뒤(아래)에 와야 답안 버튼이 stamp 유지
     */
    [data-testid="stMarkdown"]:has(.quest-hint-zone) ~ [data-testid="stButton"] button {
        width: 100% !important;
        background: linear-gradient(135deg, #FFFBE6 0%, #FFF1B0 100%) !important;
        border: 2px dashed #C97064 !important;
        border-radius: 14px !important;
        padding: 11px 16px !important;
        margin: 4px 0 8px 0 !important;
        color: #6A1F18 !important;
        font-family: 'Gowun Batang', serif !important;
        font-size: 13.5px !important;
        font-weight: 700 !important;
        box-shadow: 2px 2px 0 #C97064 !important;
        transition: all 0.12s ease-out !important;
        white-space: normal !important;
        min-height: 44px !important;
    }
    [data-testid="stMarkdown"]:has(.quest-hint-zone) ~ [data-testid="stButton"] button:hover {
        background: linear-gradient(135deg, #FFE9A6 0%, #FFD55A 100%) !important;
        border-style: solid !important;
        transform: translate(-1px, -1px) !important;
        box-shadow: 3px 3px 0 #6A1F18 !important;
    }
    [data-testid="stMarkdown"]:has(.quest-hint-zone) ~ [data-testid="stButton"] button:active {
        transform: translate(2px, 2px) !important;
        box-shadow: 0 0 0 #C97064 !important;
    }
    /* hint-end 이후 stButton: hint 스타일 reset (답안 stamp 가 곧 덮어쓸 것) */
    [data-testid="stMarkdown"]:has(.quest-hint-end) ~ [data-testid="stButton"] button {
        background: revert !important;
        border: revert !important;
        border-radius: revert !important;
        padding: revert !important;
        color: revert !important;
        font-size: revert !important;
        font-weight: revert !important;
        box-shadow: revert !important;
        min-height: revert !important;
    }

    /* ── 4지선다 답안 — Streamlit 기본 버튼을 도장(스탬프) 카드로 ──
     * Streamlit DOM:
     *   stVerticalBlock > stMarkdown(quest-opts-zone 안) > div > div.quest-opts-zone
     *   stVerticalBlock > stButton  ← SIBLING of stMarkdown, NOT quest-opts-zone
     * 따라서 .quest-opts-zone ~ [stButton] 은 형제 매칭 실패. 대신 `:has()` 로
     * quest-opts-zone 을 가진 stMarkdown 자체를 잡고, 그 형제 stButton 들을 타깃.
     * (Chrome 105+/Safari 15.4+/Firefox 121+ 지원)
     */
    [data-testid="stMarkdown"]:has(.quest-opts-zone) ~ [data-testid="stButton"] button {
        width: 100% !important;
        text-align: left !important;
        padding: 14px 18px !important;
        margin-bottom: 6px !important;
        background: linear-gradient(135deg, #FFFDF6 0%, #FFF7E2 100%) !important;
        border: 2.5px solid var(--ink) !important;
        border-radius: 14px !important;
        box-shadow: 3px 3px 0 var(--ink) !important;
        color: var(--ink) !important;
        font-family: 'Gowun Batang', serif !important;
        font-size: 15.5px !important;
        font-weight: 500 !important;
        line-height: 1.55 !important;
        transition: transform 0.12s, box-shadow 0.12s, background 0.12s !important;
        white-space: normal !important;
        min-height: 50px;
        word-break: keep-all !important;
        animation: opt-fade-up 0.4s ease-out backwards;
    }
    [data-testid="stMarkdown"]:has(.quest-opts-zone) ~ [data-testid="stButton"] button:hover {
        transform: translate(-2px, -2px) rotate(-0.4deg);
        box-shadow: 5px 5px 0 var(--ink) !important;
        background: linear-gradient(135deg, #FFF7DA 0%, #FFE9A6 100%) !important;
        border-color: var(--red-deep) !important;
        animation: opt-wiggle 0.5s ease-in-out;
    }
    @keyframes opt-wiggle {
        0%, 100% { transform: translate(-2px, -2px) rotate(-0.4deg); }
        25% { transform: translate(-3px, -2px) rotate(0.6deg); }
        75% { transform: translate(-1px, -3px) rotate(-0.8deg); }
    }
    [data-testid="stMarkdown"]:has(.quest-opts-zone) ~ [data-testid="stButton"] button:active {
        transform: translate(3px, 3px) !important;
        box-shadow: 0 0 0 var(--ink) !important;
        background: linear-gradient(135deg, #FFE7A0 0%, #FFD55A 100%) !important;
        transition: all 0.05s ease-out !important;
    }
    @keyframes opt-fade-up {
        0% { opacity: 0; transform: translateY(8px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    /* zone-end 마커가 있는 stMarkdown 형제 이후 stButton 은 stamp 리셋 */
    [data-testid="stMarkdown"]:has(.quest-opts-end) ~ [data-testid="stButton"] button {
        text-align: center !important;
        padding: revert !important;
        background: revert !important;
        border: revert !important;
        border-radius: revert !important;
        box-shadow: revert !important;
        font-size: revert !important;
        font-weight: revert !important;
        min-height: revert !important;
        animation: none !important;
    }

    /* ── 정답 시 컨페티 (master/companion 칭호 화면용) ── */
    .quest-ending.celebration {
        position: relative;
        overflow: visible;
    }
    .quest-ending.celebration::before,
    .quest-ending.celebration::after {
        content: '🎉 ✨ 🎊 🌟 ✦ 🎉 ✨ 🎊 🌟 ✦';
        position: absolute;
        left: 0; right: 0;
        text-align: center;
        font-size: 22px;
        letter-spacing: 18px;
        animation: confetti-drift 4s ease-in-out infinite;
        pointer-events: none;
    }
    .quest-ending.celebration::before {
        top: -28px;
        animation-delay: 0s;
    }
    .quest-ending.celebration::after {
        bottom: -28px;
        animation-delay: 1.5s;
        font-size: 18px;
    }
    @keyframes confetti-drift {
        0%, 100% { opacity: 0.5; transform: translateY(0); }
        50% { opacity: 0.9; transform: translateY(-4px); }
    }

    /* 힌트 영역 — 태그(사용함/잠금) */
    .hint-tag {
        font-family: 'Gowun Batang', serif;
        font-size: 13.5px;
        padding: 11px 16px;
        border-radius: 14px;
        border: 2px dashed var(--ink-soft);
        text-align: center;
        margin: 4px 0 8px 0;
        font-weight: 600;
    }
    .hint-used-tag {
        background: #DDF0CB;
        color: #2E6418;
        border-color: #2E6418;
        border-style: solid;
    }
    .hint-locked-tag {
        background: #F0EDE6;
        color: var(--ink-soft);
        opacity: 0.85;
    }
    /* (힌트 버튼 :has() 스타일은 cascade 순서상 답안 stamp 보다 위에 정의 —
     * 본 파일에서는 .quest-opts-zone 답안 stamp 규칙 BEFORE 에 위치) */

    /* 힌트로 제외된 선지 */
    .opt-eliminated {
        padding: 12px 16px;
        margin: 4px 0;
        border-radius: 14px;
        border: 2px dashed #BFBAB1;
        background: #F4F2EE;
        color: #9A958C;
        font-family: 'Gowun Batang', serif;
        font-size: 14px;
        text-decoration: line-through;
    }
    .opt-eliminated small {
        text-decoration: none;
        font-size: 11.5px;
        opacity: 0.7;
        margin-left: 6px;
    }

    /* 선지별 코멘트 (오답 비교형) */
    .opt-notes-block {
        background: #FBF7F2;
        border: 2px solid var(--ink);
        border-radius: 14px;
        padding: 12px 14px;
        margin-bottom: 14px;
        font-family: 'Gowun Batang', serif;
    }
    .opt-note-row {
        display: flex; gap: 10px; align-items: flex-start;
        padding: 8px 0;
        border-bottom: 1px dashed rgba(58,42,31,0.18);
    }
    .opt-note-row:last-child { border-bottom: none; }
    .opt-note-mark {
        flex: 0 0 22px; height: 22px; line-height: 20px;
        text-align: center;
        background: #FFFCF0;
        border: 1.5px solid var(--ink);
        border-radius: 5px;
        font-size: 13px;
    }
    .opt-note-row b { color: var(--ink); font-size: 13.5px; }
    .opt-note-row small {
        font-size: 12.5px; line-height: 1.5; color: var(--ink-soft);
    }
    .opt-note-row.note-correct .opt-note-mark {
        background: #DDF0CB; border-color: #2E6418;
    }
    .opt-note-row.note-correct b { color: #2E6418; }

    /* 엔딩 화면 */
    .quest-ending {
        display: flex; gap: 22px; align-items: center;
        background: #FFF7DA;
        border: 3px solid var(--ink);
        border-radius: 22px;
        padding: 24px 28px;
        margin: 12px 0 18px 0;
        box-shadow: 5px 5px 0 var(--ink);
    }
    .quest-ending .ending-char {
        flex: 0 0 150px;
        animation: float-y 4s ease-in-out infinite;
    }
    /* tier 전용 일러스트는 부드러운 그림자로 강조 */
    .quest-ending .ending-char img {
        max-width: 100%; height: auto;
        filter: drop-shadow(0 4px 6px rgba(58, 42, 31, 0.15));
    }
    .quest-ending .ending-text { flex: 1; }
    .quest-ending .ending-text h3 {
        margin: 0;
        font-family: 'Yeon Sung', serif;
        font-size: 24px; color: var(--ink);
    }
    .quest-ending .ending-score {
        margin: 8px 0 4px 0;
        font-family: 'Gowun Batang', serif;
        font-size: 16px; color: var(--ink);
    }
    .quest-ending .ending-tier {
        margin: 6px 0 0 0;
        font-family: 'Yeon Sung', serif;
        font-size: 22px; color: var(--red-deep);
    }
    .quest-ending .ending-meta {
        display: flex; flex-wrap: wrap; gap: 6px;
        margin-top: 10px;
    }
    .quest-ending .end-pill {
        display: inline-flex; align-items: center;
        background: #FFF7DA;
        border: 1.5px dashed var(--ink);
        border-radius: 999px;
        padding: 3px 12px;
        font-family: 'Gowun Batang', serif;
        font-size: 12.5px;
        color: var(--ink);
    }
    @media (max-width: 720px) {
        .quest-ending { flex-direction: column; text-align: center; }
        .quest-ending .ending-meta { justify-content: center; }
    }

    /* ── 왜 사초 AI? 차별 가치 카드 ────────────────────────── */
    .why-card {
        background: #FBF7F2;
        border: 2.5px solid var(--ink);
        border-radius: 22px;
        padding: 18px 22px;
        margin: 18px 0 22px 0;
        box-shadow: 4px 4px 0 var(--ink);
    }
    .why-card .why-head {
        display: flex; align-items: baseline; gap: 12px;
        margin-bottom: 14px; flex-wrap: wrap;
        border-bottom: 1.5px dashed rgba(58,42,31,0.20);
        padding-bottom: 10px;
    }
    .why-card .why-title {
        font-family: 'Yeon Sung', 'Black Han Sans', serif;
        font-size: 24px; color: var(--ink); letter-spacing: 0.5px;
    }
    .why-card .why-sub {
        font-family: 'Nanum Pen Script', cursive;
        font-size: 17px; color: var(--ink-soft);
    }
    .why-card .why-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
    }
    .why-card .why-cell {
        display: flex; gap: 12px; align-items: flex-start;
        background: #FFFCF5;
        border: 1.5px dashed rgba(58,42,31,0.22);
        border-radius: 14px;
        padding: 12px 14px;
    }
    .why-card .why-num {
        flex: 0 0 28px; height: 28px; line-height: 26px;
        text-align: center;
        background: var(--mustard);
        border: 2px solid var(--ink);
        border-radius: 50%;
        font-family: 'Gowun Batang', serif;
        font-weight: 700;
        box-shadow: 1.5px 1.5px 0 var(--ink);
    }
    .why-card .why-cell b {
        font-family: 'Gowun Batang', serif;
        font-size: 14.5px;
        color: var(--red-deep);
    }
    .why-card .why-cell p {
        margin: 4px 0 0 0;
        font-size: 13.5px;
        line-height: 1.55;
        color: var(--ink);
    }
    @media (max-width: 720px) {
        .why-card .why-grid { grid-template-columns: 1fr; }
    }

    /* ── 추천 질문 카드 그리드 (캐릭터 + 버튼 묶음) ────────── */
    /* 모바일에서 추천 질문 column 강제 세로 스택 */
    @media (max-width: 720px) {
        .suggest-section ~ [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: 8px !important;
        }
        .suggest-section ~ [data-testid="stHorizontalBlock"] > div {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        /* 모바일에선 캐릭터 작게 */
        .suggest-section ~ [data-testid="stHorizontalBlock"] .suggest-char svg {
            width: 60px !important; height: 60px !important;
        }
    }
    .suggest-section h5 {
        font-family: 'Gowun Batang', serif;
        font-size: 17px; margin: 8px 0 6px 0;
    }
    .suggest-char {
        text-align: center;
        margin-bottom: -6px;
        pointer-events: none;
        height: 70px; display: flex; align-items: flex-end; justify-content: center;
    }
    .suggest-char:nth-child(1) { animation: tilt-a 5s ease-in-out infinite; }
    .suggest-char:nth-child(2) { animation: tilt-b 5.5s ease-in-out infinite; }
    @keyframes tilt-a {
        0%, 100% { transform: rotate(-3deg); }
        50% { transform: rotate(3deg); }
    }
    @keyframes tilt-b {
        0%, 100% { transform: rotate(2deg) translateY(0); }
        50% { transform: rotate(-2deg) translateY(-3px); }
    }

    /* ── 모든 stButton — 도장 클릭 느낌 ─────────────────── */
    .stButton > button {
        border-radius: 16px !important;
        border: 2.5px solid var(--ink) !important;
        background: var(--cream) !important;
        color: var(--ink) !important;
        font-family: 'Gowun Batang', serif !important;
        font-weight: 600 !important;
        font-size: 14.5px !important;
        box-shadow: 3px 3px 0 var(--ink) !important;
        transition: transform 0.08s, box-shadow 0.08s, background 0.15s !important;
        padding: 10px 14px !important;
        min-height: 56px !important;
        line-height: 1.45 !important;
        white-space: normal !important;
    }
    .stButton > button:hover {
        transform: translate(-1px, -1px) !important;
        box-shadow: 4px 4px 0 var(--ink) !important;
        background: #FFF3CF !important;
    }
    .stButton > button:active {
        transform: translate(2px, 2px) !important;
        box-shadow: 1px 1px 0 var(--ink) !important;
    }
    .stDownloadButton > button {
        background: #FFE7A0 !important;
    }

    /* ── 채팅 메시지 풍선화 ──────────────────────────────── */
    [data-testid="stChatMessage"] {
        background: var(--cream);
        border: 2.5px solid var(--ink);
        border-radius: 22px;
        box-shadow: 3px 3px 0 var(--ink);
        padding: 14px 18px !important;
        margin: 0 0 18px 0 !important;
        font-family: 'Gowun Batang', serif;
        font-size: 15.5px; line-height: 1.75;
    }
    /* 사용자 메시지 — 살짝 따뜻한 톤 */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: #FFECDD;
    }
    [data-testid="stChatMessage"] img,
    [data-testid="stChatMessage"] [data-testid^="chatAvatarIcon"] {
        border: 2px solid var(--ink) !important;
        border-radius: 50% !important;
        background: var(--cream) !important;
        box-shadow: 2px 2px 0 var(--ink) !important;
    }

    /* ── 사실 확인 스티커 배지 ────────────────────────── */
    .badge-sticker {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 4px 12px 4px 6px;
        border: 2px solid var(--ink);
        border-radius: 999px;
        font-family: 'Gowun Batang', serif;
        font-weight: 700; font-size: 13.5px;
        box-shadow: 2px 2px 0 var(--ink);
        margin: 2px 0 8px 0;
        animation: pop-in 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
        transform-origin: left center;
    }
    .badge-sticker .badge-icon {
        display: inline-flex; align-items: center; justify-content: center;
        width: 22px; height: 22px;
        background: #FFF;
        border: 1.5px solid var(--ink);
        border-radius: 50%;
    }
    .badge-sticker .badge-icon svg { width: 16px; height: 16px; }
    @keyframes pop-in {
        0%   { transform: scale(0.3) rotate(-20deg); opacity: 0; }
        70%  { transform: scale(1.1) rotate(3deg); opacity: 1; }
        100% { transform: scale(1) rotate(0); opacity: 1; }
    }

    /* ── 사료 두루마리 카드 ──────────────────────────── */
    .evidence-card {
        background:
            repeating-linear-gradient(0deg,
                transparent 0, transparent 26px,
                rgba(201, 112, 100, 0.05) 26px, rgba(201, 112, 100, 0.05) 27px),
            linear-gradient(180deg, #FBF1D8 0%, #F0DDB0 100%);
        border: 2.5px solid var(--ink);
        border-radius: 14px;
        padding: 14px 18px;
        margin: 12px 0;
        box-shadow: 3px 3px 0 var(--mustard);
        position: relative;
        font-family: 'Gowun Batang', serif;
        /* 등장 시 부드럽게 fade + 살짝 위에서 떨어짐 */
        animation: card-drop-in 0.5s ease-out backwards;
        transition: transform 0.18s ease-out, box-shadow 0.18s ease-out;
    }
    @keyframes card-drop-in {
        0% { opacity: 0; transform: translateY(-8px) scale(0.985); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    /* hover lift — 두루마리가 책상에서 살짝 떠오르듯 */
    .evidence-card:hover {
        transform: translate(-2px, -3px);
        box-shadow: 5px 6px 0 var(--mustard),
                    0 8px 16px rgba(58,42,31,0.10);
    }
    .evidence-card::before, .evidence-card::after {
        content: '';
        position: absolute; top: -1px; bottom: -1px; width: 6px;
        background: repeating-linear-gradient(180deg,
            #5C4A38 0 8px, #2A1F18 8px 16px);
        border: 1px solid var(--ink);
    }
    .evidence-card::before { left: -8px; border-radius: 3px 0 0 3px; }
    .evidence-card::after  { right: -8px; border-radius: 0 3px 3px 0; }
    .evidence-card h4 {
        color: var(--red-deep);
        margin: 0 0 6px 0; font-size: 15.5px; font-weight: 700;
    }
    .evidence-card .meta {
        color: var(--ink-soft); font-size: 12.5px; margin-bottom: 8px;
        font-family: 'Noto Sans KR', sans-serif;
    }
    .evidence-card .body { font-size: 14.5px; line-height: 1.7; }
    .evidence-card a {
        color: var(--red-deep); text-decoration: none; font-weight: 700;
        border-bottom: 1.5px dotted var(--red-deep);
    }
    .evidence-card h4 code {
        background: rgba(58,42,31,0.08);
        padding: 1px 6px;
        border-radius: 5px;
        font-size: 12.5px;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        color: var(--ink-soft);
        margin-right: 4px;
    }
    /* 출처 검증 영역 — 본 솔루션의 핵심 차별점 */
    .evidence-card .verify-row {
        display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
        margin-top: 12px; padding-top: 10px;
        border-top: 1.5px dashed rgba(58,42,31,0.18);
    }
    .evidence-card .verify-btn {
        display: inline-flex; align-items: center;
        padding: 7px 14px;
        background: var(--mustard);
        color: var(--ink) !important;
        border: 2px solid var(--ink);
        border-radius: 10px;
        box-shadow: 2px 2px 0 var(--ink);
        font-family: 'Gowun Batang', serif;
        font-weight: 700;
        font-size: 13.5px;
        text-decoration: none !important;
        transition: transform 0.08s;
    }
    .evidence-card .verify-btn:hover {
        background: #FFD55A;
        transform: translate(-1px, -1px);
        box-shadow: 3px 3px 0 var(--ink);
        border-bottom: 2px solid var(--ink) !important;
    }
    .evidence-card .verify-btn:active {
        transform: translate(1px, 1px);
        box-shadow: 1px 1px 0 var(--ink);
    }
    .evidence-card .source-authority {
        font-size: 12px;
        color: var(--ink-soft);
        font-family: 'Noto Sans KR', sans-serif;
    }
    /* 지도·사진 검색 링크 */
    .evidence-card .place-row {
        display: flex; gap: 8px; flex-wrap: wrap;
        margin-top: 10px;
    }
    .evidence-card .place-link {
        display: inline-block;
        padding: 5px 11px;
        background: #FFFCF0;
        color: var(--ink) !important;
        border: 1.5px solid var(--ink-soft);
        border-radius: 999px;
        font-family: 'Gowun Batang', serif;
        font-size: 12.5px;
        font-weight: 600;
        text-decoration: none !important;
        border-bottom: 1.5px solid var(--ink-soft) !important;
        transition: background 0.12s;
    }
    .evidence-card .place-link:hover {
        background: #FFE7A0;
        border-color: var(--ink) !important;
    }
    /* 카카오맵 / 로드뷰 — 노란 강조 (Kakao 브랜드 컬러 톤) */
    .evidence-card .place-link.kakao-link {
        background: #FFE500;
        border-color: #3C2A1E !important;
        color: #3C2A1E !important;
    }
    .evidence-card .place-link.kakao-link:hover {
        background: #FFD200;
    }
    .evidence-card .place-link.roadview-link {
        background: #E8F0FE;
        border-color: #3A6FB8 !important;
        color: #1E3A6F !important;
    }
    .evidence-card .place-link.roadview-link:hover {
        background: #C4D8F5;
    }
    .evidence-card .license-tag {
        margin-top: 6px;
        font-size: 11.5px;
        color: #8a7560;
        font-family: 'Noto Sans KR', sans-serif;
    }
    /* 원문·라이선스 접기 — 정보 과부하 감소 */
    .evidence-card .evidence-details {
        margin: 8px 0 4px 0;
        background: #FBF7EC;
        border: 1px dashed rgba(58,42,31,0.20);
        border-radius: 8px;
        padding: 4px 12px;
        font-family: 'Gowun Batang', serif;
    }
    .evidence-card .evidence-details summary {
        cursor: pointer;
        font-size: 12.5px;
        color: var(--ink-soft);
        padding: 4px 0;
        outline: none;
        list-style: none;
    }
    .evidence-card .evidence-details summary::-webkit-details-marker {
        display: none;
    }
    .evidence-card .evidence-details summary::before {
        content: '▸ ';
        display: inline-block;
        transition: transform 0.15s;
        color: var(--mustard);
        font-weight: 700;
    }
    .evidence-card .evidence-details[open] summary::before {
        transform: rotate(90deg);
    }
    .evidence-card .evidence-details summary:hover {
        color: var(--ink);
    }
    .evidence-card .evidence-details[open] {
        padding-bottom: 10px;
    }
    /* 공모전 특별제공 데이터셋 칩 (한복·국악·문양) */
    .evidence-card .dataset-chips {
        display: flex; flex-wrap: wrap; gap: 6px;
        margin: 6px 0 8px 0;
    }
    .evidence-card .dataset-chip {
        display: inline-block;
        padding: 3px 10px;
        font-family: 'Gowun Batang', serif;
        font-size: 11.5px;
        font-weight: 700;
        color: #5C3A1F;
        background: linear-gradient(135deg, #FFE8C6, #FFD9A6);
        border: 1px solid #C78A4E;
        border-radius: 999px;
        letter-spacing: 0.2px;
        box-shadow: 0 1px 0 rgba(58,42,31,0.06);
    }
    .evidence-card .dataset-chip.nearby-chip {
        background: linear-gradient(135deg, #D4E8C9, #A8D894);
        border-color: #5A7A3B;
        color: #2E4A1A;
    }

    /* ── 응답 메타 (품삯 띠) ──────────────────────────── */
    .meta-row {
        display: inline-flex; gap: 14px; flex-wrap: wrap;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 16px; color: var(--ink);
        background: #FFF7DA;
        border: 1.5px dashed var(--ink);
        border-radius: 999px;
        padding: 4px 14px; margin: 8px 0 0 0;
    }
    .meta-row b { color: var(--red-deep); font-weight: 700; }

    /* ── thinking ─────────────────────────────────── */
    .thinking {
        display: inline-flex; align-items: center; gap: 10px;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 19px; color: var(--ink); opacity: 0.85;
        margin: 4px 0;
    }
    .thinking-char {
        animation: bounce-walk 0.6s ease-in-out infinite;
    }
    @keyframes bounce-walk {
        0%, 100% { transform: translateY(0) rotate(-2deg); }
        50% { transform: translateY(-3px) rotate(2deg); }
    }
    .thinking-dots::after {
        content: '…'; display: inline-block;
        animation: dot-pulse 1.4s infinite steps(4);
    }
    @keyframes dot-pulse {
        0%   { content: '.'; }
        25%  { content: '..'; }
        50%  { content: '…'; }
        75%  { content: '…—'; }
        100% { content: '.'; }
    }

    /* ── 푸터 — 부드러운 한 줄 ───────────────────────── */
    .footer-strip {
        display: inline-flex; align-items: center; gap: 12px;
        background: transparent;
        padding: 18px 6px 6px 6px;
        margin: 28px auto 0 auto;
        font-family: 'Nanum Pen Script', cursive;
    }
    .footer-strip .footer-char {
        flex: 0 0 44px;
        animation: bounce-walk 0.7s ease-in-out infinite;
        opacity: 0.85;
    }
    .footer-strip .footer-text {
        font-size: 19px; line-height: 1.4; color: var(--ink-soft);
        letter-spacing: 0.2px;
    }
    .footer-attrib {
        max-width: 880px;
        margin: 6px auto 18px auto;
        padding: 10px 14px;
        font-family: 'Gowun Batang', serif;
        font-size: 11.5px;
        line-height: 1.6;
        color: rgba(58,42,31,0.7);
        background: rgba(255, 244, 222, 0.55);
        border: 1px dashed rgba(58,42,31,0.18);
        border-radius: 8px;
        text-align: left;
    }
    .footer-attrib::before { display: none; }

    /* ── 여백 데코 캐릭터 (좌·우) ───────────────────── */
    .deco-left, .deco-right {
        position: fixed;
        pointer-events: none;
        z-index: 1;
        opacity: 0.65;
    }
    .deco-left { left: 12px; bottom: 20px; }
    .deco-right { right: 12px; bottom: 80px; transform: scaleX(-1); }
    @media (max-width: 980px) {
        .deco-left, .deco-right { display: none; }
    }

    /* ── 채팅 input — 인라인 카드 스타일 (sticky 바닥 해제) ── */
    /* Streamlit이 기본으로 입력칸을 화면 하단에 고정시켜 푸터를 가립니다.
       static 으로 풀어 자연스럽게 흐름 안에 위치시킵니다. */
    [data-testid="stBottomBlockContainer"],
    [data-testid="stBottomBlock"] {
        position: static !important;
        background: transparent !important;
        padding: 0 !important;
        max-width: none !important;
    }
    [data-testid="stChatInput"] {
        margin: 18px 0 12px 0 !important;
        padding: 0 !important;
    }
    /* 입력 박스 외형 — 중립 회색 (베이지 카드와 시각적으로 구분) */
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInputContainer"] {
        background: #ECEAE5 !important;
        border: 2px solid #BFBAB1 !important;
        border-radius: 18px !important;
        box-shadow: none !important;
        overflow: hidden;
    }
    /* 텍스트 영역 자체 */
    [data-testid="stChatInput"] textarea {
        background: transparent !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        font-family: 'Gowun Batang', serif !important;
        font-size: 16px !important;
        color: var(--ink) !important;
        padding: 16px 20px !important;
        min-height: 56px !important;
        line-height: 1.6 !important;
    }
    [data-testid="stChatInput"] textarea::placeholder {
        color: var(--ink-soft) !important;
        opacity: 0.7;
        font-style: italic;
    }
    /* 보내기 버튼 (화살표) */
    [data-testid="stChatInput"] button {
        background: var(--mustard) !important;
        border: 2px solid var(--ink) !important;
        border-radius: 50% !important;
        box-shadow: 2px 2px 0 var(--ink) !important;
        color: var(--ink) !important;
        margin: 8px 8px 8px 0 !important;
        transition: transform 0.08s !important;
    }
    [data-testid="stChatInput"] button:hover {
        background: #FFD55A !important;
        transform: translate(-1px, -1px);
        box-shadow: 3px 3px 0 var(--ink) !important;
    }
    [data-testid="stChatInput"] button:active {
        transform: translate(1px, 1px);
        box-shadow: 1px 1px 0 var(--ink) !important;
    }
    [data-testid="stChatInput"] button svg {
        fill: var(--ink) !important;
        color: var(--ink) !important;
    }

    /* ─── 📜 사료 보관함 페이지 ─── */
    .collection-header {
        display: flex; align-items: center; gap: 16px;
        background: #FBF7F2;          /* 캐릭터 배경과 동일 */
        border: 2.5px solid var(--ink);
        border-radius: 22px;
        padding: 18px 22px;
        box-shadow: 4px 4px 0 var(--ink);
        margin: 6px 0 18px 0;
        position: relative;
    }
    .collection-char { flex: 0 0 70px; animation: wobble 5s ease-in-out infinite; }
    .collection-char-side {
        flex: 0 0 60px; opacity: 0.85;
        animation: peek-wobble 6s ease-in-out infinite;
    }
    .collection-head-text { flex: 1; }
    .collection-head-text h3 {
        margin: 0; font-size: 22px; font-weight: 700;
        font-family: 'Gowun Batang', serif;
    }
    .collection-head-text p {
        margin: 4px 0 0 0;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 19px; color: var(--ink-soft);
    }
    .collection-head-text b { color: var(--red-deep); font-weight: 700; }

    .collection-empty {
        display: flex; gap: 18px; align-items: center;
        background: var(--cream);
        border: 2.5px dashed var(--ink);
        border-radius: 22px;
        padding: 32px 28px;
        margin: 12px 0 18px 0;
        text-align: left;
    }
    .collection-empty-char {
        flex: 0 0 120px;
        animation: float-y 5s ease-in-out infinite;
    }
    .collection-empty-text { flex: 1; }
    .collection-empty-text h3 {
        margin: 0; font-family: 'Gowun Batang', serif;
        font-size: 19px; color: var(--ink);
    }
    .collection-empty-text p {
        margin: 6px 0 0 0;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 18px; color: var(--ink-soft);
    }

    @media (max-width: 720px) {
        .collection-header { flex-wrap: wrap; }
        .collection-char-side { display: none; }
        .collection-empty { flex-direction: column; text-align: center; }
    }

    /* ─── 🔐 비밀번호 게이트 (세련·귀엽게) ─── */
    /* 상단 브랜드 스트립 */
    .gate-brand {
        display: flex; justify-content: center; align-items: center;
        gap: 14px;
        padding: 8px 0 14px 0;
        margin-bottom: 12px;
    }
    .gate-brand-mark {
        animation: brand-bob 4s ease-in-out infinite;
    }
    @keyframes brand-bob {
        0%, 100% { transform: translateY(0) rotate(-2deg); }
        50% { transform: translateY(-3px) rotate(2deg); }
    }
    .gate-brand-text h1 {
        margin: 0;
        font-family: 'Yeon Sung', 'Black Han Sans', serif;
        font-size: 32px;
        color: var(--ink);
        letter-spacing: 1px;
        line-height: 1.1;
    }
    .gate-brand-text p {
        margin: 4px 0 0 0;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 17px;
        color: var(--ink-soft);
        opacity: 0.85;
    }

    /* 캐릭터 카드 반짝임 (sparkles) */
    .gate-sparkle {
        position: absolute;
        color: var(--mustard);
        text-shadow: 0 0 6px rgba(219, 184, 113, 0.6);
        pointer-events: none;
        opacity: 0;
        animation: gate-sparkle 3.5s ease-in-out infinite;
    }
    .gate-sparkle.s1 { top: 20%; left: 8%;  font-size: 18px; animation-delay: 0s; }
    .gate-sparkle.s2 { top: 60%; right: 10%; font-size: 14px; animation-delay: 1.2s; }
    .gate-sparkle.s3 { top: 80%; left: 18%; font-size: 16px; animation-delay: 2.4s; }
    @keyframes gate-sparkle {
        0%, 100% { opacity: 0; transform: scale(0.4) rotate(0deg); }
        50%      { opacity: 0.85; transform: scale(1) rotate(25deg); }
    }

    /* 대문 처마 (지붕) */
    .door-card .door-eaves {
        position: absolute;
        top: -16px; left: -10px; right: -10px;
        height: 12px;
        background: linear-gradient(180deg, #2A1F18 0%, #1A130E 100%);
        border-radius: 8px 8px 4px 4px;
        box-shadow: 0 3px 0 rgba(58,42,31,0.3);
    }

    /* 가치 카드 — icon 분리 셀, 그라데이션 */
    .gate-why-cell {
        display: flex; gap: 12px; align-items: flex-start;
        background: linear-gradient(135deg, #FFFCF5 0%, #FFF6E0 100%) !important;
        border: 1.5px dashed rgba(58,42,31,0.20) !important;
        border-radius: 14px;
        padding: 12px 14px !important;
        transition: transform 0.15s, box-shadow 0.15s;
    }
    .gate-why-cell:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(58,42,31,0.08);
        border-color: var(--mustard) !important;
    }
    .gate-why-cell .why-icon {
        flex: 0 0 36px; height: 36px;
        display: flex; align-items: center; justify-content: center;
        background: var(--mustard);
        border: 2px solid var(--ink);
        border-radius: 50%;
        font-size: 18px;
        box-shadow: 1.5px 1.5px 0 var(--ink);
    }
    .gate-why-cell .why-body { flex: 1; }
    .gate-why-cell .why-body b {
        font-family: 'Gowun Batang', serif;
        font-size: 14.5px;
        color: var(--red-deep) !important;
    }
    .gate-why-cell .why-body p {
        margin: 4px 0 0 0;
        font-family: 'Gowun Batang', serif;
        font-size: 12.5px;
        line-height: 1.55;
        color: var(--ink);
    }

    /* 오늘의 한 줄 인용 */
    .gate-quote {
        max-width: 720px;
        margin: 22px auto 8px auto;
        padding: 20px 28px 18px 28px;
        background: linear-gradient(135deg, #FFFCF5 0%, #F7F0E0 100%);
        border-left: 4px solid var(--mustard);
        border-radius: 4px 14px 14px 4px;
        box-shadow: 0 2px 6px rgba(58,42,31,0.05);
        position: relative;
    }
    .gate-quote-mark {
        position: absolute;
        top: -10px; left: 14px;
        font-family: 'Gowun Batang', serif;
        font-size: 42px;
        color: var(--mustard);
        line-height: 1;
        text-shadow: 0 1px 0 #FFF, 0 2px 0 var(--ink);
    }
    .gate-quote-text {
        font-family: 'Gowun Batang', serif;
        font-size: 16px;
        line-height: 1.6;
        color: var(--ink);
        font-style: italic;
    }
    .gate-quote-who {
        margin-top: 8px;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 16px;
        color: var(--ink-soft);
        text-align: right;
    }
    /* 외국어 모드: 한국어 인용 아래 영문 한 줄 부제 */
    .gate-quote-gloss {
        margin-top: 6px;
        padding-top: 6px;
        border-top: 1px dashed rgba(140,106,60,0.30);
        font-family: 'Gowun Batang', 'Georgia', serif;
        font-size: 13px;
        line-height: 1.5;
        color: var(--ink-soft);
        font-style: italic;
    }

    .gate-wrap {
        padding: 12px 4px 40px 4px;
    }
    .gate-card {
        width: 100%;
        background: #FBF7F2;     /* 캐릭터 PNG 배경과 동일한 베이지 */
        border: 3px solid var(--ink);
        border-radius: 24px;
        padding: 22px 24px 20px 24px;
        box-shadow: 5px 5px 0 var(--ink);
        position: relative;
        overflow: visible;
        height: 100%;
    }
    /* ── 우측 대문 (한옥 솟을대문 풍) ── */
    .door-card {
        position: relative;
        background:
            repeating-linear-gradient(180deg,
                rgba(0,0,0,0.04) 0 22px,
                rgba(0,0,0,0.10) 22px 24px),
            linear-gradient(180deg, #C97064 0%, #A8554A 100%);
        border: 3px solid var(--ink);
        border-radius: 14px 14px 8px 8px;
        padding: 26px 22px 18px 22px;
        box-shadow: 5px 5px 0 var(--ink);
        height: 100%;
        min-height: 240px;
    }
    /* 대문 윗부분 처마 같은 띠 */
    .door-card::before {
        content: '';
        position: absolute; top: -8px; left: -3px; right: -3px;
        height: 10px;
        background: var(--ink);
        border-radius: 6px 6px 0 0;
    }
    /* 가운데 세로선 (양 문짝 경계) */
    .door-card::after {
        content: '';
        position: absolute; top: 18px; bottom: 12px;
        left: 50%; width: 2px;
        background: rgba(42,31,24,0.45);
        transform: translateX(-50%);
        pointer-events: none;
    }
    .door-card .door-knob {
        position: absolute; right: 16px; top: 56%;
        width: 14px; height: 14px; border-radius: 50%;
        background: var(--mustard);
        border: 2px solid var(--ink);
        box-shadow: 1px 1px 0 var(--ink);
    }
    .door-card .door-hinges {
        position: absolute; left: 8px; top: 22px; bottom: 22px;
        display: flex; flex-direction: column; justify-content: space-between;
    }
    .door-card .door-hinges span {
        display: block; width: 6px; height: 18px;
        background: var(--ink); border-radius: 2px;
    }
    .door-card .door-title {
        text-align: center;
        font-family: 'Yeon Sung', serif;
        font-size: 22px; color: #FFF8E5;
        text-shadow: 1.5px 1.5px 0 var(--ink);
        margin-bottom: 4px;
    }
    .door-card .door-sub {
        text-align: center;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 16px; color: #FFE9DD;
        margin-bottom: 14px;
    }
    .door-card .door-err {
        margin-top: 10px;
        background: rgba(255,255,255,0.92);
        border: 1.5px dashed var(--ink);
        border-radius: 10px;
        padding: 8px 12px;
        text-align: center;
        font-family: 'Gowun Batang', serif;
        font-size: 13px;
        color: #8C2A18;
    }
    /* 대문 안 입력칸 — 종이 색으로 도드라지게 */
    .door-card [data-testid="stTextInput"] input {
        background: #FFFDF6 !important;
        border: 2px solid var(--ink) !important;
        border-radius: 10px !important;
        text-align: center !important;
        font-family: 'Gowun Batang', serif !important;
        letter-spacing: 3px;
        font-size: 16px !important;
        padding: 11px 14px !important;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.08) !important;
    }
    /* 대문 안 제출 버튼 */
    .door-card [data-testid="stFormSubmitButton"] button {
        width: 100%;
        margin-top: 6px;
        background: var(--mustard) !important;
        color: var(--ink) !important;
        border: 2px solid var(--ink) !important;
        border-radius: 10px !important;
        box-shadow: 2px 2px 0 var(--ink) !important;
        font-family: 'Gowun Batang', serif !important;
        font-weight: 700 !important;
    }
    .door-card [data-testid="stFormSubmitButton"] button:hover {
        background: #FFD55A !important;
        transform: translate(-1px, -1px);
        box-shadow: 3px 3px 0 var(--ink) !important;
    }
    .gate-card::after {
        content: ''; position: absolute; inset: 8px;
        border: 1.5px dashed rgba(42, 31, 24, 0.22);
        border-radius: 22px; pointer-events: none;
    }
    .gate-chars {
        display: flex; align-items: flex-end; justify-content: center;
        gap: 14px; margin-bottom: 10px;
    }
    .gate-chars .char-main {
        animation: float-y 4s ease-in-out infinite;
    }
    .gate-chars .char-lock {
        animation: lock-wiggle 3.5s ease-in-out infinite;
        margin-bottom: 22px;  /* 살짝 띄워서 사관 키와 맞춤 */
        transform-origin: center;
    }
    @keyframes lock-wiggle {
        0%, 100% { transform: rotate(-4deg) translateY(0); }
        50%      { transform: rotate(6deg) translateY(-3px); }
    }
    .gate-bubble {
        background: #FFF;
        border: 2.5px solid var(--ink);
        border-radius: 18px;
        padding: 14px 18px;
        font-family: 'Gowun Batang', serif;
        font-size: 15.5px; line-height: 1.7;
        text-align: center; color: var(--ink);
        margin: 4px 4px 14px 4px;
        box-shadow: 2px 2px 0 var(--ink);
        position: relative;
    }
    .gate-bubble::before {
        content: '';
        position: absolute; left: 50%; top: -10px;
        transform: translateX(-50%);
        width: 0; height: 0;
        border-left: 10px solid transparent;
        border-right: 10px solid transparent;
        border-bottom: 12px solid var(--ink);
    }
    .gate-bubble::after {
        content: '';
        position: absolute; left: 50%; top: -7px;
        transform: translateX(-50%);
        width: 0; height: 0;
        border-left: 9px solid transparent;
        border-right: 9px solid transparent;
        border-bottom: 11px solid #FFF;
    }
    .gate-bubble small {
        display: block; margin-top: 6px;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 16px; color: var(--ink-soft); opacity: 0.85;
    }
    /* 입력칸 — 동글동글 */
    .gate-card [data-testid="stTextInput"] input {
        border-radius: 14px !important;
        border: 2.5px solid var(--ink) !important;
        background: #FFFDF6 !important;
        font-family: 'Gowun Batang', serif !important;
        font-size: 16px !important;
        padding: 12px 16px !important;
        box-shadow: 2px 2px 0 var(--ink) !important;
        text-align: center !important;
        letter-spacing: 2px;
    }
    .gate-card [data-testid="stTextInput"] input:focus {
        outline: none !important;
        border-color: var(--red-deep) !important;
        background: #FFF7E0 !important;
    }
    /* 제출 버튼 */
    .gate-card [data-testid="stFormSubmitButton"] button {
        width: 100%;
        border-radius: 14px !important;
        border: 2.5px solid var(--ink) !important;
        background: #FFE7A0 !important;
        color: var(--ink) !important;
        font-family: 'Gowun Batang', serif !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        box-shadow: 3px 3px 0 var(--ink) !important;
        padding: 12px 18px !important;
        margin-top: 8px;
        transition: all 0.1s !important;
    }
    .gate-card [data-testid="stFormSubmitButton"] button:hover {
        background: #FFD55A !important;
        transform: translate(-1px, -1px);
        box-shadow: 4px 4px 0 var(--ink) !important;
    }
    .gate-card [data-testid="stFormSubmitButton"] button:active {
        transform: translate(2px, 2px);
        box-shadow: 1px 1px 0 var(--ink) !important;
    }
    /* 틀렸을 때 흔들리기 */
    .gate-shake { animation: shake 0.55s cubic-bezier(.36,.07,.19,.97); }
    @keyframes shake {
        10%, 90% { transform: translateX(-2px); }
        20%, 80% { transform: translateX(3px); }
        30%, 50%, 70% { transform: translateX(-6px); }
        40%, 60% { transform: translateX(6px); }
    }

    /* ───────── 게이트 v2 — 한옥 지붕·풍경·꽃잎·두루마리·도장 ───────── */
    /* 브랜드 라인 + 오늘 날짜 태그 */
    .gate-brand-wrap {
        display: flex; flex-direction: column; align-items: center;
        gap: 4px;
        margin: 4px 0 16px 0;
        position: relative; z-index: 2;
    }
    .gate-brand-tag {
        display: inline-flex; gap: 8px; align-items: center;
        padding: 4px 14px;
        background: #FFF7DA;
        border: 1.5px dashed rgba(58,42,31,0.35);
        border-radius: 999px;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 14.5px;
        color: var(--ink);
        opacity: 0.85;
    }
    .brand-tag-dot { color: var(--mustard); font-weight: 700; }

    /* 떨어지는 꽃잎·종이조각 — 절제된 무드 (z-index 0, 매우 약함) */
    .gate-petals {
        position: fixed; inset: 0; pointer-events: none;
        z-index: 0; overflow: hidden;
    }
    .gate-petals .petal {
        position: absolute;
        top: -32px;
        font-size: 15px;
        opacity: 0;
        animation: petal-fall 18s linear infinite;
        filter: drop-shadow(0 1px 1px rgba(0,0,0,0.05));
    }
    .gate-petals .p1 { left: 6%;  font-size: 14px; animation-delay: 0s;  }
    .gate-petals .p2 { left: 18%; font-size: 17px; animation-delay: 2.5s; animation-duration: 21s; }
    .gate-petals .p3 { left: 31%; font-size: 13px; animation-delay: 5s;  animation-duration: 16s; }
    .gate-petals .p4 { left: 44%; font-size: 12px; animation-delay: 1s;  animation-duration: 22s; }
    .gate-petals .p5 { left: 58%; font-size: 16px; animation-delay: 7s;  animation-duration: 19s; }
    .gate-petals .p6 { left: 71%; font-size: 14px; animation-delay: 3s;  animation-duration: 23s; }
    .gate-petals .p7 { left: 83%; font-size: 11px; animation-delay: 9s;  animation-duration: 17s; }
    .gate-petals .p8 { left: 92%; font-size: 15px; animation-delay: 5.5s; animation-duration: 20s; }
    @keyframes petal-fall {
        0%   { transform: translateY(-32px) rotate(0deg);    opacity: 0; }
        8%   { opacity: 0.55; }
        92%  { opacity: 0.55; }
        100% { transform: translateY(110vh) rotate(420deg);  opacity: 0; }
    }

    /* 본 게이트 콘텐츠는 꽃잎 위로 */
    .gate-brand-wrap, .gate-card, .door-wrap,
    .gate-why, .gate-quote, .gate-foot,
    [data-testid="stExpander"] { position: relative; z-index: 2; }

    /* ── 한옥 대문 — 지붕·풍경·단청 메달 ── */
    .door-wrap {
        position: relative;
        padding-top: 36px;     /* 지붕 공간 */
        height: 100%;
    }
    .door-roof {
        position: absolute;
        top: 0; left: -12px; right: -12px;
        height: 36px;
        pointer-events: none;
    }
    /* 기와 곡선 — clip-path 로 솟을대문 처마 곡선 흉내 */
    .door-roof .roof-tile {
        position: absolute; inset: 6px 0 0 0;
        background:
            repeating-linear-gradient(90deg,
                rgba(255,255,255,0.10) 0 6px,
                rgba(0,0,0,0.18) 6px 7px),
            linear-gradient(180deg, #5A3F28 0%, #3A2A1F 100%);
        border: 2px solid #1A130E;
        border-radius: 4px 4px 0 0;
        clip-path: polygon(0% 100%, 6% 30%, 24% 14%, 50% 0%, 76% 14%, 94% 30%, 100% 100%);
        box-shadow: inset 0 -3px 0 rgba(0,0,0,0.25);
    }
    /* 용마루 가운데 단청 캡 */
    .door-roof .roof-cap {
        position: absolute; top: -2px; left: 50%;
        width: 18px; height: 14px;
        background: linear-gradient(180deg, #C97064 0%, #8C1D18 100%);
        border: 2px solid #1A130E;
        border-radius: 50% 50% 4px 4px;
        transform: translateX(-50%);
        box-shadow: 0 1px 0 rgba(0,0,0,0.3);
    }
    /* 추녀 끝에 매달린 풍경(風磬) */
    .door-roof .roof-chime {
        position: absolute; right: 6px; top: 26px;
        font-size: 18px;
        transform-origin: top center;
        animation: chime-swing 3.2s ease-in-out infinite;
        filter: drop-shadow(0 1px 2px rgba(0,0,0,0.25));
    }
    @keyframes chime-swing {
        0%, 100% { transform: rotate(-14deg); }
        50%      { transform: rotate(16deg); }
    }

    /* 대문 카드 자체 — 기존 .door-card 와 함께 동작 */
    .door-wrap .door-card { height: calc(100% - 36px); }

    /* 두 짝 문 — 양쪽 둥근 문고리 (배치 수정) */
    .door-card .door-knob {
        position: absolute; top: 56%;
        width: 14px; height: 14px; border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #F2D58A, var(--mustard));
        border: 2px solid var(--ink);
        box-shadow: 1px 1px 0 var(--ink),
                    inset 0 0 0 1px rgba(255,255,255,0.4);
    }
    .door-card .door-knob.left  { left:  calc(50% - 22px); right: auto; }
    .door-card .door-knob.right { right: calc(50% - 22px); left:  auto; }

    /* 두 짝 문 — 양쪽 경첩(좌·우 모두) */
    .door-card .door-hinges {
        position: absolute; top: 22px; bottom: 22px;
        display: flex; flex-direction: column; justify-content: space-between;
    }
    .door-card .door-hinges.left  { left: 6px; }
    .door-card .door-hinges.right { right: 6px; }
    .door-card .door-hinges span {
        background:
            linear-gradient(180deg, #2A1F18 0%, #6A4A28 50%, #2A1F18 100%);
    }

    /* 가운데 단청 꽃 메달 — 문 양쪽이 만나는 지점 장식 */
    .door-card .door-medallion {
        position: absolute;
        top: 50%; left: 50%;
        width: 46px; height: 46px;
        transform: translate(-50%, -50%);
        pointer-events: none;
        opacity: 0.85;
    }
    .door-card .door-medallion .med-petal {
        position: absolute;
        top: 50%; left: 50%;
        width: 18px; height: 18px;
        background: linear-gradient(135deg, #FFE7A0, #C97064);
        border: 1.5px solid #1A130E;
        border-radius: 60% 0 60% 0;
        transform-origin: center;
    }
    .door-card .door-medallion .med-petal:nth-child(1) {
        transform: translate(-50%, -50%) rotate(0deg) translate(0, -10px);
    }
    .door-card .door-medallion .med-petal:nth-child(2) {
        transform: translate(-50%, -50%) rotate(90deg) translate(0, -10px);
    }
    .door-card .door-medallion .med-petal:nth-child(3) {
        transform: translate(-50%, -50%) rotate(180deg) translate(0, -10px);
    }
    .door-card .door-medallion .med-petal:nth-child(4) {
        transform: translate(-50%, -50%) rotate(270deg) translate(0, -10px);
    }
    .door-card .door-medallion .med-core {
        position: absolute;
        top: 50%; left: 50%;
        width: 14px; height: 14px;
        background: radial-gradient(circle at 35% 35%, #FFE9A6, var(--mustard));
        border: 2px solid var(--ink);
        border-radius: 50%;
        transform: translate(-50%, -50%);
        box-shadow: 0 1px 0 rgba(0,0,0,0.3),
                    inset 0 0 0 1.5px rgba(255,255,255,0.4);
    }

    /* 도장형 에러 — 빨간 직인 분위기 */
    .door-card .door-err {
        position: relative;
        display: flex; align-items: center; gap: 8px;
        justify-content: center;
    }
    .door-card .door-err-stamp {
        background: #B0322A; color: #FFF;
        padding: 1px 8px;
        font-family: 'Yeon Sung', serif;
        font-size: 12px;
        border-radius: 4px;
        letter-spacing: 1px;
        transform: rotate(-3deg);
        box-shadow: 1px 1px 0 rgba(0,0,0,0.3);
    }
    .door-card .door-err-tag {
        background: #FFF7DA; color: #8C2A18;
        padding: 1px 8px;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 13px;
        border: 1px dashed #B0322A;
        border-radius: 4px;
        transform: rotate(2deg);
    }

    /* ── 두루마리 인용 — 위·아래 막대 + 직인 ── */
    .gate-scroll-wrap {
        max-width: 720px;
        margin: 24px auto 8px auto;
        position: relative;
    }
    .gate-scroll-wrap .scroll-rod {
        height: 14px;
        background: linear-gradient(180deg, #6A4A28 0%, #3A2A18 100%);
        border: 2px solid #1A130E;
        border-radius: 8px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.15),
                    0 1px 2px rgba(0,0,0,0.2);
        position: relative;
    }
    .gate-scroll-wrap .scroll-rod::before,
    .gate-scroll-wrap .scroll-rod::after {
        content: '';
        position: absolute;
        top: -3px; bottom: -3px;
        width: 8px;
        background: linear-gradient(180deg, #8C6A3C 0%, #6A4A28 50%, #3A2A18 100%);
        border: 2px solid #1A130E;
        border-radius: 50%;
    }
    .gate-scroll-wrap .scroll-rod::before { left: -10px; }
    .gate-scroll-wrap .scroll-rod::after  { right: -10px; }
    .gate-scroll-wrap .scroll-rod-top    { margin-bottom: -1px; }
    .gate-scroll-wrap .scroll-rod-bottom { margin-top: -1px; }

    /* 기존 .gate-quote 위에 두루마리 종이 느낌 덧입힘 */
    .gate-scroll-wrap .gate-quote {
        max-width: none;
        margin: 0 8px;
        padding: 26px 36px 22px 36px;
        background:
            radial-gradient(ellipse at top, rgba(140,106,60,0.10), transparent 60%),
            radial-gradient(ellipse at bottom, rgba(140,106,60,0.10), transparent 60%),
            linear-gradient(180deg, #FBF1D8 0%, #F2E2BC 100%);
        border: 2px solid #8C6A3C;
        border-left: 4px solid #8C6A3C;
        border-right: 4px solid #8C6A3C;
        border-radius: 2px;
        box-shadow: inset 0 0 0 1px rgba(140,106,60,0.20),
                    inset 0 -10px 14px rgba(140,106,60,0.06),
                    2px 2px 0 rgba(140,106,60,0.25);
    }
    /* 직인 도장 */
    .gate-quote .gate-quote-seal {
        position: absolute;
        top: 10px; right: 18px;
        width: 42px; height: 42px;
        background: #B0322A;
        border: 2.5px solid #6A1F18;
        border-radius: 6px;
        color: #FFE9A6;
        font-family: 'Yeon Sung', 'Black Han Sans', serif;
        font-size: 13px;
        display: flex; align-items: center; justify-content: center;
        transform: rotate(-9deg);
        letter-spacing: 1.5px;
        box-shadow: 0 0 0 1.5px #B0322A inset,
                    0 2px 0 rgba(0,0,0,0.25);
        text-shadow: 0 0 1px rgba(0,0,0,0.4);
        opacity: 0.92;
    }

    /* ── 사관실 도장 푸터 ── */
    .gate-foot {
        display: flex; align-items: center; justify-content: center;
        gap: 12px; flex-wrap: wrap;
        margin: 28px auto 4px auto;
        opacity: 0.85;
        position: relative; z-index: 2;
    }
    .gate-foot .foot-stamp {
        background: #B0322A;
        color: #FFE9A6;
        padding: 3px 12px;
        font-family: 'Yeon Sung', 'Black Han Sans', serif;
        font-size: 13px;
        letter-spacing: 3px;
        border-radius: 4px;
        transform: rotate(-3deg);
        box-shadow: 1.5px 1.5px 0 rgba(0,0,0,0.3),
                    inset 0 0 0 1px rgba(255,255,255,0.15);
        text-shadow: 0 0 1px rgba(0,0,0,0.4);
    }
    .gate-foot .foot-stamp-jade {
        background: #2E6418;
        color: #FFF8E0;
        transform: rotate(4deg);
        font-size: 11.5px;
        letter-spacing: 1.5px;
        padding: 3px 10px;
    }
    .gate-foot .foot-tag {
        font-family: 'Nanum Pen Script', cursive;
        font-size: 14px;
        color: var(--ink-soft);
    }
    @media (max-width: 720px) {
        .gate-petals { display: none; }   /* 모바일은 거슬리니 끔 */
        .door-roof .roof-chime { right: 0; }
        .gate-foot { gap: 8px; }
        .gate-foot .foot-tag { display: none; }
    }
    .gate-err {
        background: #FFE3D6;
        border: 2px dashed #C97064;
        border-radius: 14px;
        padding: 10px 14px;
        font-family: 'Gowun Batang', serif;
        text-align: center;
        margin-top: 10px;
        color: #7A3A2A;
        font-size: 14.5px;
    }
    .gate-foot {
        margin-top: 14px; text-align: center;
        font-family: 'Nanum Pen Script', cursive;
        font-size: 16px; color: var(--ink-soft); opacity: 0.7;
    }
    /* 게이트 안쪽 Why + How-to-play */
    .gate-why {
        margin-top: 18px;
        padding-top: 16px;
        border-top: 2px dashed rgba(58,42,31,0.20);
    }
    .gate-why-head {
        display: flex; align-items: baseline; gap: 12px;
        margin-bottom: 12px; flex-wrap: wrap;
    }
    .gate-why-title {
        font-family: 'Yeon Sung', 'Black Han Sans', serif;
        font-size: 22px; color: var(--ink); letter-spacing: 0.4px;
    }
    .gate-why-sub {
        font-family: 'Nanum Pen Script', cursive;
        font-size: 17px; color: var(--ink-soft);
    }
    .gate-why-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        margin-bottom: 14px;
    }
    .gate-why-cell {
        background: #FFFCF5;
        border: 1.5px dashed rgba(58,42,31,0.22);
        border-radius: 12px;
        padding: 10px 12px;
        font-family: 'Gowun Batang', serif;
    }
    .gate-why-cell b {
        font-size: 13.5px; color: var(--red-deep);
    }
    .gate-why-cell p {
        margin: 4px 0 0 0;
        font-size: 12.5px; line-height: 1.5; color: var(--ink);
    }
    .gate-howto {
        background: #FFF7DA;
        border: 1.5px solid var(--ink);
        border-radius: 12px;
        padding: 12px 16px;
        font-family: 'Gowun Batang', serif;
    }
    .gate-howto b {
        display: block; margin-bottom: 6px;
        font-size: 14px; color: var(--ink);
    }
    .gate-howto ol {
        margin: 4px 0 0 18px; padding: 0;
        font-size: 13px; line-height: 1.7; color: var(--ink);
    }
    @media (max-width: 720px) {
        .gate-why-grid { grid-template-columns: 1fr; }
    }

    /* ── 게이트 언어 토글 (국기) — 우측 상단 ── */
    .gate-lang-row {
        display: flex; justify-content: flex-end;
        margin: -4px 0 6px 0;
        position: relative; z-index: 3;
    }
    /* 모바일: 토글이 좁아져도 깨지지 않게 — 컬럼 간격·패딩 0 */
    @media (max-width: 720px) {
        .gate-lang-row { margin: 0 0 8px 0; }
        .gate-lang-row [data-testid="stHorizontalBlock"] {
            gap: 2px !important;
        }
        .gate-lang-row [data-testid="stHorizontalBlock"] > div {
            padding: 0 1px !important;
        }
        .gate-lang-row [data-testid="stButton"] button {
            font-size: 14px !important;
            padding: 2px 4px !important;
            min-height: 28px !important;
        }
    }
    /* Streamlit 기본 button 위에 토글 스타일 덧입힘 (게이트 내부만) */
    [data-testid="stHorizontalBlock"] > div [data-testid="stButton"] button[kind="secondary"][data-testid*="gate_lang"],
    button[kind="secondary"]:has(> div:contains("🇰🇷")),
    button[kind="secondary"]:has(> div:contains("🇺🇸")),
    button[kind="secondary"]:has(> div:contains("🇯🇵")),
    button[kind="secondary"]:has(> div:contains("🇨🇳")) {
        /* :has 미지원 브라우저용 폴백 — 아래 일반 .gate-lang-row 규칙이 덮음 */
    }
    .gate-lang-row [data-testid="stButton"] button {
        font-size: 16px !important;
        padding: 4px 6px !important;
        min-height: 30px !important;
        background: #FBF7F2 !important;
        border: 1.5px solid var(--ink-soft) !important;
        border-radius: 8px !important;
        box-shadow: 1.5px 1.5px 0 rgba(58,42,31,0.15) !important;
        color: var(--ink) !important;
        font-weight: 600;
    }
    .gate-lang-row [data-testid="stButton"] button:hover {
        background: #FFF7DA !important;
        border-color: var(--mustard) !important;
    }

    /* ── Streamlit 기본 스피너 — 사관 스타일로 ── */
    [data-testid="stSpinner"] {
        text-align: center;
        padding: 10px 14px;
        background: linear-gradient(135deg, #FFFCEF 0%, #FFF7DA 100%);
        border: 2px dashed var(--ink);
        border-radius: 14px;
        margin: 12px 0;
        box-shadow: 2px 2px 0 rgba(58,42,31,0.15);
    }
    [data-testid="stSpinner"] > div {
        display: inline-flex !important; align-items: center; gap: 12px;
        font-family: 'Gowun Batang', serif !important;
        font-size: 14.5px !important;
        color: var(--ink) !important;
    }
    /* 스피너 회전 아이콘 — 두루마리 느낌 */
    [data-testid="stSpinner"] svg, [data-testid="stSpinner"] i {
        color: var(--red-deep) !important;
        animation: scroll-spin 1.4s linear infinite;
    }
    @keyframes scroll-spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* ── 게이트 1줄 티저 (접힘 상태에서도 가치 노출) ── */
    .gate-teaser {
        display: flex; flex-wrap: wrap; gap: 6px;
        justify-content: center;
        margin: 16px auto 8px auto;
        max-width: 720px;
        position: relative; z-index: 2;
    }
    .gate-teaser .teaser-pill {
        background: #FFF7DA;
        border: 1.5px dashed var(--ink-soft);
        border-radius: 999px;
        padding: 4px 12px;
        font-family: 'Gowun Batang', serif;
        font-size: 12.5px;
        color: var(--ink);
        white-space: nowrap;
    }
    /* expander 내부 섹션 헤더 */
    .gate-section-h {
        margin: 4px 0 8px 0 !important;
        border: none !important;
        font-family: 'Yeon Sung', 'Gowun Batang', serif !important;
        font-size: 16px !important;
        color: var(--red-deep) !important;
    }

    /* ── 데이터 출처 · 차별성 매트릭스 (게이트/popover 공용) ── */
    .data-sources {
        font-family: 'Gowun Batang', serif;
        color: var(--ink);
    }
    .sources-tbl {
        width: 100%;
        border-collapse: collapse;
        font-size: 12.5px;
        line-height: 1.55;
        background: #FFFCEF;
        border: 1.5px solid var(--ink);
        border-radius: 10px;
        overflow: hidden;
    }
    .sources-tbl th {
        background: #FFE9A6;
        color: var(--ink);
        font-weight: 800;
        text-align: left;
        padding: 8px 10px;
        border-bottom: 1.5px solid var(--ink);
        font-family: 'Gaegu', 'Gowun Batang', serif;
        font-size: 13px;
    }
    .sources-tbl td {
        padding: 8px 10px;
        border-bottom: 1px dashed rgba(58,42,31,0.25);
        vertical-align: top;
    }
    .sources-tbl tbody tr:last-child td { border-bottom: none; }
    .sources-tbl tbody tr:nth-child(odd) { background: rgba(255, 247, 218, 0.45); }
    .sources-tbl b { color: #6B4226; }
    .sources-note {
        margin-top: 10px;
        padding: 8px 12px;
        background: #FFF3D0;
        border-left: 4px solid #C97064;
        border-radius: 6px;
        font-size: 12px;
        color: var(--ink);
    }

    /* 모바일 폴백 */
    @media (max-width: 720px) {
        .hero { flex-direction: column; align-items: flex-start; }
        .hero-char { align-self: center; flex: 0 0 110px; }
        .hero-peek { display: none; }
        .greeting-card { flex-direction: column; align-items: stretch; }
        .greeting-bubble::before, .greeting-bubble::after { display: none; }
        .topbar { flex-wrap: wrap; gap: 8px; }
        /* 톱바 7컬럼 모바일 잘림 방지 — 폰트·패딩 축소 */
        .topbar-tools .topbar-logo .brand { font-size: 20px !important; }
        .topbar-tools .topbar-logo .brand-sub { display: none; }
        .topbar-tools .topbar-logo .logo-svg svg { width: 36px !important; height: 36px !important; }
        .topbar-tools [data-baseweb="select"] > div { min-height: 32px !important; font-size: 12.5px !important; }
        .topbar-tools button { padding: 6px 8px !important; font-size: 13px !important; min-height: 32px !important; }
        /* 컬럼 간격 좁힘 */
        .topbar-tools [data-testid="stHorizontalBlock"] { gap: 4px !important; }
        .topbar-tools [data-testid="stHorizontalBlock"] > div { padding: 0 2px !important; }
    }
    /* 더 좁은 폰 (≤420px) — 브랜드 텍스트만 숨김, 로고는 유지 */
    @media (max-width: 420px) {
        .topbar-tools .topbar-logo .brand { font-size: 16px !important; letter-spacing: 0 !important; }
        .topbar-tools [data-baseweb="select"] > div { min-height: 28px !important; font-size: 11.5px !important; padding: 0 6px !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────
# 세션 상태
# ─────────────────────────────────────────────────────────────
def init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "language" not in st.session_state:
        st.session_state.language = "ko"
    if "mode" not in st.session_state:
        st.session_state.mode = "일반"
    if "show_rag_debug" not in st.session_state:
        st.session_state.show_rag_debug = False
    if "show_map" not in st.session_state:
        st.session_state.show_map = True
    if "view" not in st.session_state:
        st.session_state.view = "quest"         # "quest" | "chat" | "collection"
    if "collection" not in st.session_state:
        st.session_state.collection = {}
    # ─── 퀘스트 게임 상태 ───
    if "credits" not in st.session_state:
        st.session_state.credits = 0
    if "streak" not in st.session_state:
        st.session_state.streak = 0
    if "best_streak" not in st.session_state:
        st.session_state.best_streak = 0
    if "total_attempts" not in st.session_state:
        st.session_state.total_attempts = 0
    if "total_correct" not in st.session_state:
        st.session_state.total_correct = 0
    if "current_q" not in st.session_state:
        st.session_state.current_q = None
    if "q_answered" not in st.session_state:
        st.session_state.q_answered = False
    if "q_user_choice" not in st.session_state:
        st.session_state.q_user_choice = None
    if "q_seen_ids" not in st.session_state:
        st.session_state.q_seen_ids = []
    if "quest_theme" not in st.session_state:
        st.session_state.quest_theme = "all"
    # ─── 힌트 / 코스 모드 ───
    if "eliminated_options" not in st.session_state:
        st.session_state.eliminated_options = []
    if "play_mode" not in st.session_state:
        st.session_state.play_mode = "course"        # "theme" | "course"
    if "course_id" not in st.session_state:
        st.session_state.course_id = "jeongdong"
    if "course_idx" not in st.session_state:
        st.session_state.course_idx = 0
    if "course_score" not in st.session_state:
        st.session_state.course_score = 0
    if "course_finished" not in st.session_state:
        st.session_state.course_finished = False
    # ─── 시간 추적 ───
    if "q_start_time" not in st.session_state:
        st.session_state.q_start_time = None
    if "last_elapsed" not in st.session_state:
        st.session_state.last_elapsed = 0.0
    if "last_bonus" not in st.session_state:
        st.session_state.last_bonus = 0
    if "user_geo" not in st.session_state:
        st.session_state.user_geo = None  # (lat, lon) or None
    # ─── 랜딩 지도 표시 상태 ───
    if "landing_map_collapsed" not in st.session_state:
        st.session_state.landing_map_collapsed = False
    if "landing_map_expanded" not in st.session_state:
        st.session_state.landing_map_expanded = False


init_state()
T = UI_TEXT[st.session_state.language]
api_key_present = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


# ─────────────────────────────────────────────────────────────
# 로고 클릭 → 첫 화면(인사 화면) 복귀 (auth/언어/모드는 유지)
# ─────────────────────────────────────────────────────────────
if st.query_params.get("home") == "1":
    st.session_state.messages = []
    st.session_state.view = "chat"
    st.query_params.clear()


# ─────────────────────────────────────────────────────────────
# 🔐 비밀번호 게이트 — APP_PASSWORD 가 설정돼 있을 때만 발동
# ─────────────────────────────────────────────────────────────
def _expected_password() -> str:
    try:
        v = st.secrets.get("APP_PASSWORD", None)
        if v:
            return str(v).strip()
    except Exception:
        pass
    return os.getenv("APP_PASSWORD", "").strip()


def _data_sources_html() -> str:
    """공공데이터 9종 출처 표 — 게이트·⚙ popover 공용."""
    return (
        '<div class="data-sources">'
        '<table class="sources-tbl">'
        '<thead><tr>'
        '<th>출처</th><th>제공기관</th><th>활용 방식</th><th>라이선스</th>'
        '</tr></thead>'
        '<tbody>'
        '<tr><td><b>조선왕조실록 정보</b></td>'
        '<td>국사편찬위원회</td>'
        '<td>1차 사료 원문·번역 인용 (sillok-/hist-)</td>'
        '<td>공공데이터포털 — 제한 없음</td></tr>'
        '<tr><td><b>승정원일기</b></td>'
        '<td>국사편찬위원회</td>'
        '<td>국왕 일과·정사 보조 사료</td>'
        '<td>공공데이터포털 — 제한 없음</td></tr>'
        '<tr><td><b>한국사데이터베이스</b></td>'
        '<td>국사편찬위원회</td>'
        '<td>고려사·근대사 보조 사료 (hist-/mod-)</td>'
        '<td>db.history.go.kr · 학술 인용</td></tr>'
        '<tr><td><b>한국고전종합DB</b></td>'
        '<td>한국고전번역원</td>'
        '<td>문집·일성록 등 인용 보강</td>'
        '<td>itkc.or.kr · 학술 인용</td></tr>'
        '<tr><td><b>문화재 공간정보</b></td>'
        '<td>문화재청·궁능유적본부</td>'
        '<td>장소 좌표·경복궁/덕수궁 내부 7방 (gbg-/dsg-)</td>'
        '<td>공공데이터포털 — 제한 없음</td></tr>'
        '<tr><td><b>관광정보 TourAPI 4.0</b> '
        '<span style="background:#5A7A3B;color:#fff;font-size:10px;'
        'padding:1px 6px;border-radius:6px;margin-left:4px;">실시간 호출</span></td>'
        '<td>한국관광공사 (KorService2)</td>'
        '<td>좌표 반경 500m 등재 명소 자동 enrichment + 다국어 안내</td>'
        '<td>data.go.kr · 출처 표기</td></tr>'
        '<tr><td><b>국립국악원 자료</b></td>'
        '<td>국립국악원</td>'
        '<td>K-콘텐츠 카드 음악/장단 배경 (kculture-)</td>'
        '<td>공공누리 1유형</td></tr>'
        '<tr><td><b>한복·전통문양</b></td>'
        '<td>한국공예·디자인문화진흥원</td>'
        '<td>캐릭터·UI 모티프 + K-콘텐츠 설명</td>'
        '<td>공공누리 1·2유형</td></tr>'
        '<tr><td><b>지자체 향토 사료</b></td>'
        '<td>경주시·단양군·안동시 등</td>'
        '<td>도보 코스 단서 (경주 5릉·단양 8경)</td>'
        '<td>지자체 개방 자료</td></tr>'
        '</tbody></table>'
        '<div class="sources-note">'
        '  모든 사료 카드 하단에 <b>원문 링크</b>와 <b>출처 라이선스</b>를 명시합니다. '
        '  학설이 갈리는 사안은 <b>양측 견해를 함께</b> 노출합니다.'
        '</div>'
        '</div>'
    )


def _diff_matrix_html(corpus_n: int) -> str:
    """범용 AI vs 사초 AI 차별성 매트릭스 — 게이트·⚙ popover 공용."""
    return (
        '<div class="data-sources">'
        '<table class="sources-tbl">'
        '<thead><tr>'
        '<th>축</th><th>범용 AI<br>(ChatGPT·Gemini·Perplexity)</th>'
        '<th>오디오가이드<br>(KTO Odii)</th>'
        '<th>위치게임<br>(Questo·Adventure Lab)</th>'
        '<th><b>사초 AI</b></th>'
        '</tr></thead>'
        '<tbody>'
        '<tr><td><b>1차 사료 인용</b></td>'
        '<td>불확실·환각 위험</td><td>해설형</td><td>없음</td>'
        '<td><b>매 답변 원문 링크 + 라이선스</b></td></tr>'
        '<tr><td><b>학설 다양성</b></td>'
        '<td>단일 답변 강요</td><td>공식 견해만</td><td>—</td>'
        '<td><b>갈리는 사안 양측 견해</b></td></tr>'
        '<tr><td><b>현장 위치 게임</b></td>'
        '<td>없음</td><td>수동 청취</td><td>있음</td>'
        '<td><b>GPS + 도보 권역 코스 8종</b></td></tr>'
        '<tr><td><b>한국사 사전 큐레이션</b></td>'
        '<td>일반 웹</td><td>관광지 중심</td><td>없음</td>'
        f'<td><b>{corpus_n}건 사료·콘텐츠 카드</b></td></tr>'
        '<tr><td><b>다국어 동시 검증</b></td>'
        '<td>언어별 품질 편차</td><td>4~8개</td><td>29개(영문 중심)</td>'
        '<td><b>한·영·일·중 동시 + 학설 라벨 번역</b></td></tr>'
        '</tbody></table>'
        '<div class="sources-note">'
        '  <b>핵심</b>: 검증된 도시 탐험 게임 모델 × 한국사 사료 검증 × AI 무한 출제. '
        '  한국형 위치기반 학습 게임 시장의 첫 사료 검증형 솔루션.'
        '</div>'
        '</div>'
    )


# ── 게이트 다국어 — 사관 대사·도장·티저 (한·영·일·중) ──
_GATE_I18N: dict[str, dict] = {
    "ko": {
        "tagline": "한국사 사료 검증형 퀴즈 게임 · Korean-history Quest",
        "brand_place": "🏯 사관실 · 종로",
        "date_fmt": "%Y년 %m월 %d일",
        "greetings": [
            ("어어… <b>누구세요…?</b>",
             "사관 두루마리에 들려면 우측 <b>대문</b>에 암호를 살짝 속삭여 주시구려."),
            ("음… <b>낯이 익은 듯도 한데…</b>",
             "기억이 가물가물하오. 어쨌든 우측 대문에 암호 한 자 적어 주시오."),
            ("어허, <b>드디어 깨우셨소.</b>",
             "곤히 자던 사관이외다… 우측 대문 안에 암호를 적어 주시오."),
            ("실은 말이오, <b>이 두루마리…</b>",
             "잘못된 손에 들어가면 큰일이오. 우측 대문에 암호를 적어 주오."),
            ("어어, <b>관계자시오?</b>",
             "사초는 함부로 펼 수 없는 것이외다. 우측 대문에 암호를 적어 주시오."),
        ],
        "error_lines": [
            None,
            ("어어… <b>그 암호가 아니오.</b>",
             "혹시 한·영 자판이 잘못된 건 아닌지… 한 번만 더."),
            ("정말이오…? <b>두 번째 틀리셨소.</b>",
             "비밀번호는 한 자 한 자… 천천히 적으시오. 사관도 놀라오."),
            ("…음. <b>이쯤 되면 사관도 의심하오.</b>",
             "관계자분이면 아실 텐데… 진짜 마지막으로 한 번만 더?"),
            ("허허… <b>이거 참 곤란하오.</b>",
             "사초는 함부로 보일 수 없소. 관계자께 한 번 더 여쭤 보오."),
            ("…<b>외인이시구려.</b>",
             "사관실 문은 닫겠소이다. 진정한 관계자께만 열리는 문이외다."),
        ],
        "door_title": "🏯 사관실 대문",
        "door_sub": "암호를 속삭여 주오",
        "submit_first": "🗝 들여 보내 주시오",
        "submit_retry": "🗝 다시 한 번",
        "door_err_text": "어어… 그 암호가 아닌 듯하오…",
        "stamp_words": ["한 번 더", "위험", "출입 금지"],
        "bubble_hint": "(Whisper the password at the door →)",
        "teaser": [
            "🎮 매번 새 문제",
            "🗺 도보 코스 {course_n}종",
            "🔍 사료 {corpus_n}건 검증",
            "⚖ 학설 양면",
        ],
        "info_expander": "✨ 사초 AI는 무엇이오? — 가치·노는 법·데이터·차별성 한꺼번에",
        "foot_jade": "관계자 외 출입 금지",
        "foot_tag": "Office of the Records · 사초 AI · v2",
    },
    "en": {
        "tagline": "Korean-history quest with verified primary sources",
        "brand_place": "🏯 Sagwan Office · Jongno, Seoul",
        "date_fmt": "%b %d, %Y",
        "greetings": [
            ("Oh… <b>who's there…?</b>",
             "To unroll the scroll, whisper the password into the <b>gate</b> on the right."),
            ("Hmm… <b>have we met before?</b>",
             "My memory's fuzzy. Either way — kindly enter the password on the right."),
            ("Ah, you've <b>finally woken me up.</b>",
             "This Sagwan was deep asleep… please enter the password on the right."),
            ("Truth is, <b>this scroll…</b>",
             "It mustn't fall into wrong hands. Please enter the password."),
            ("Are you, perhaps, <b>a staff member?</b>",
             "The chronicles aren't for everyone. Please enter the password."),
        ],
        "error_lines": [
            None,
            ("Hmm… <b>that's not the password.</b>",
             "Could it be a typo? One more try."),
            ("Really…? <b>Wrong twice now.</b>",
             "Take it slowly — letter by letter."),
            ("…<b>even this Sagwan grows suspicious.</b>",
             "If you're really staff, you'd know it. Once more?"),
            ("Heh… <b>this is getting awkward.</b>",
             "The chronicles aren't for everyone. Maybe check with staff."),
            ("…<b>you are clearly an outsider.</b>",
             "This Sagwan's door is closing. Only true members may pass."),
        ],
        "door_title": "🏯 The Sagwan Gate",
        "door_sub": "Whisper the password",
        "submit_first": "🗝 Open the gate",
        "submit_retry": "🗝 Try again",
        "door_err_text": "Hm… that doesn't seem to be the password…",
        "stamp_words": ["one more", "warning", "denied"],
        "bubble_hint": "(사관 speaks in Korean — you're welcome →)",
        "teaser": [
            "🎮 Fresh question each time",
            "🗺 {course_n} walking courses",
            "🔍 {corpus_n} verified records",
            "⚖ Multiple scholarly views",
        ],
        "info_expander": "✨ What is Sacho AI? — value · how to play · data · differentiators",
        "foot_jade": "Staff only",
        "foot_tag": "Office of the Records · Sacho AI · v2",
    },
    "ja": {
        "tagline": "韓国史·原典検証クイズゲーム · Korean-history Quest",
        "brand_place": "🏯 史官室 · 鍾路",
        "date_fmt": "%Y年 %m月 %d日",
        "greetings": [
            ("おや… <b>どちらさまで…?</b>",
             "巻物を見るには、右の<b>大門</b>で合言葉をささやいてくだされ。"),
            ("はて… <b>見覚えがあるような…</b>",
             "記憶が曖昧でしてな。とにかく右の門に合言葉を。"),
            ("おお、<b>ようやく起こされたか。</b>",
             "ぐっすり寝ていた史官でござる。右の門に合言葉を。"),
            ("実はな、<b>この巻物…</b>",
             "誰彼の手に渡ってはなりませぬ。合言葉を。"),
            ("もしや、<b>関係者の方かな?</b>",
             "史草はみだりに開けぬもの。右の門に合言葉を。"),
        ],
        "error_lines": [
            None,
            ("おや… <b>合言葉が違うようで。</b>",
             "もしや入力ミス? もう一度だけ。"),
            ("本当に…? <b>二回目もはずれだ。</b>",
             "一文字ずつ慎重に。史官も驚いておるよ。"),
            ("ふむ… <b>史官も怪しんでおる。</b>",
             "関係者ならご存じのはず。最後にもう一度?"),
            ("ほっほ… <b>これは困った。</b>",
             "史草はみだりには見せられぬ。関係者にお尋ねを。"),
            ("…<b>外の方でござったか。</b>",
             "史官室の門は閉じまする。真の関係者のみに開く門。"),
        ],
        "door_title": "🏯 史官室の大門",
        "door_sub": "合言葉をささやいて",
        "submit_first": "🗝 通させていただきます",
        "submit_retry": "🗝 もう一度",
        "door_err_text": "おや… 合言葉が違うようで…",
        "stamp_words": ["もう一度", "注意", "立入禁止"],
        "bubble_hint": "(史官は韓国語で話します — どうぞ →)",
        "teaser": [
            "🎮 毎回新しい問題",
            "🗺 徒歩コース{course_n}種",
            "🔍 史料{corpus_n}件検証",
            "⚖ 両論併記",
        ],
        "info_expander": "✨ 史草AIとは? — 価値·遊び方·データ·差別化",
        "foot_jade": "関係者以外立入禁止",
        "foot_tag": "Office of the Records · 史草AI · v2",
    },
    "zh": {
        "tagline": "韩国史·原典验证问答游戏 · Korean-history Quest",
        "brand_place": "🏯 史官室 · 钟路",
        "date_fmt": "%Y年%m月%d日",
        "greetings": [
            ("咦… <b>哪位…?</b>",
             "要看卷轴,请在右侧<b>大门</b>低声说出口令。"),
            ("嗯… <b>看着有些眼熟…</b>",
             "记忆模糊了。无论如何,请在右侧大门写下口令。"),
            ("啊,<b>终于把我吵醒了。</b>",
             "睡得正香的史官在下。请在右门输入口令。"),
            ("其实呢,<b>这卷轴…</b>",
             "落入旁人之手可不行。请输入口令。"),
            ("莫非,<b>是同僚?</b>",
             "史草不可轻易示人。请在右门输入口令。"),
        ],
        "error_lines": [
            None,
            ("咦… <b>口令不对呢。</b>",
             "莫非输错? 再来一次。"),
            ("当真…? <b>第二次也错了。</b>",
             "请一字一字慢慢来。史官也吃了一惊。"),
            ("唔… <b>史官也起疑了。</b>",
             "若真是同僚定该知晓。最后一次?"),
            ("呵呵… <b>这下尴尬了。</b>",
             "史草不便轻示。请向同僚再确认。"),
            ("…<b>原来是外人。</b>",
             "史官室之门要关了。唯有同僚方可入内。"),
        ],
        "door_title": "🏯 史官室大门",
        "door_sub": "低声说出口令",
        "submit_first": "🗝 请进",
        "submit_retry": "🗝 再来一次",
        "door_err_text": "咦… 口令不对呢…",
        "stamp_words": ["再来", "警告", "禁止入内"],
        "bubble_hint": "(史官说韩语 — 欢迎您 →)",
        "teaser": [
            "🎮 每次新题",
            "🗺 步行路线{course_n}种",
            "🔍 史料{corpus_n}件验证",
            "⚖ 学说双面",
        ],
        "info_expander": "✨ 何为史草AI? — 价值·玩法·数据·差异化",
        "foot_jade": "非相关人员止步",
        "foot_tag": "Office of the Records · 史草AI · v2",
    },
}
_GATE_LANG_OPTIONS = [
    ("ko", "🇰🇷", "한국어"),
    ("en", "🇺🇸", "English"),
    ("ja", "🇯🇵", "日本語"),
    ("zh", "🇨🇳", "中文"),
]


def render_password_gate(expected: str) -> None:
    """세련된 게이트 — 브랜드 + 한옥 대문 + 회전 그리팅 + 두루마리 인용.

    한·영·일·중 4개 언어 지원 — 우측 상단 국기 토글로 전환.
    성공 시 선택 언어를 메인 앱 ``st.session_state.language`` 로 승계.
    """
    import random as _r
    from datetime import datetime as _dt

    # 게이트 언어 (메인 앱 언어와 별도로 게이트만 적용)
    if "_gate_lang" not in st.session_state:
        # 메인 앱 언어 따라가도록 초기화 (선택해 둔 게 있으면 유지)
        st.session_state._gate_lang = st.session_state.get("language", "ko")
    glang = st.session_state._gate_lang
    if glang not in _GATE_I18N:
        glang = "ko"
    GI = _GATE_I18N[glang]

    attempts = st.session_state.get("auth_attempts", 0)
    shake_class = " gate-shake" if st.session_state.pop("_just_failed", False) else ""

    # 시도 횟수가 있으면 에스컬레이션 라인, 아니면 회전 그리팅
    if attempts > 0:
        idx = min(attempts, len(GI["error_lines"]) - 1)
        line_top, line_sub = GI["error_lines"][idx]
    else:
        if "_gate_line_idx" not in st.session_state:
            st.session_state._gate_line_idx = _r.randrange(len(GI["greetings"]))
        line_top, line_sub = GI["greetings"][
            st.session_state._gate_line_idx % len(GI["greetings"])
        ]

    # 게이트 페이지: 흰 배경 + 미세한 점 패턴 (한지 결 느낌)
    st.markdown(
        '<style>'
        '.stApp { '
        '  background: '
        '    radial-gradient(rgba(58,42,31,0.035) 1px, transparent 1px),'
        '    #FFFFFF !important;'
        '  background-size: 26px 26px !important;'
        '}'
        '.stApp::before, .stApp::after { display: none; }'
        '.main .block-container { padding-top: 0.5rem !important; max-width: 980px !important; }'
        '</style>',
        unsafe_allow_html=True,
    )

    # ── 떨어지는 꽃잎·종이조각 (배경 무드) ──
    st.markdown(
        '<div class="gate-petals" aria-hidden="true">'
        '  <span class="petal p1">🌸</span>'
        '  <span class="petal p2">📜</span>'
        '  <span class="petal p3">🍂</span>'
        '  <span class="petal p4">✦</span>'
        '  <span class="petal p5">🌸</span>'
        '  <span class="petal p6">📜</span>'
        '  <span class="petal p7">✧</span>'
        '  <span class="petal p8">🍂</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── 언어 토글 (우측 상단 국기 4개) — 모바일 wide 비율로 ──
    _lang_col_l, _lang_col_r = st.columns([3, 3])
    with _lang_col_r:
        st.markdown('<div class="gate-lang-row">', unsafe_allow_html=True)
        flag_cols = st.columns(len(_GATE_LANG_OPTIONS))
        for i, (code, flag, _name) in enumerate(_GATE_LANG_OPTIONS):
            with flag_cols[i]:
                is_active = (code == glang)
                btn_label = f"{flag}" + (" ✓" if is_active else "")
                if st.button(btn_label, key=f"gate_lang_{code}",
                             use_container_width=True,
                             help=_name):
                    st.session_state._gate_lang = code
                    # 토글하면 라인도 새로 뽑음
                    st.session_state.pop("_gate_line_idx", None)
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 상단 브랜드 스트립 (현판 느낌 + 오늘 날짜) ──
    today_str = _dt.now().strftime(GI["date_fmt"])
    st.markdown(
        f'<div class="gate-brand-wrap">'
        f'  <div class="gate-brand">'
        f'    <div class="gate-brand-mark">{LOGO_SVG}</div>'
        f'    <div class="gate-brand-text">'
        f'      <h1>사초(史草) AI</h1>'
        f'      <p>{GI["tagline"]}</p>'
        f'    </div>'
        f'  </div>'
        f'  <div class="gate-brand-tag">'
        f'    <span class="brand-tag-date">📅 {today_str}</span>'
        f'    <span class="brand-tag-dot">·</span>'
        f'    <span class="brand-tag-place">{GI["brand_place"]}</span>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── 가로 두 칸: [캐릭터+말풍선] [대문(비밀번호)] ──
    gate_left, gate_right = st.columns([2.3, 1.3])

    with gate_left:
        st.markdown(
            f'<div class="gate-card{shake_class}">'
            f'  <div class="gate-sparkle s1">✦</div>'
            f'  <div class="gate-sparkle s2">✧</div>'
            f'  <div class="gate-sparkle s3">✦</div>'
            f'  <div class="gate-chars">'
            f'    <div class="char-main">{char_img("whodat", width=148)}</div>'
            f'    <div class="char-lock">{LOCK_SVG}</div>'
            f'  </div>'
            f'  <div class="gate-bubble">'
            f'    {line_top}<br>'
            f'    {line_sub}'
            f'    <small>{GI["bubble_hint"]}</small>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with gate_right:
        # 한옥 대문 — 기와 지붕 + 풍경 + 단청 메달 + 두 개의 둥근 문고리
        st.markdown(
            f'<div class="door-wrap">'
            f'  <div class="door-roof">'
            f'    <div class="roof-tile"></div>'
            f'    <div class="roof-cap"></div>'
            f'    <div class="roof-chime">🎐</div>'
            f'  </div>'
            f'  <div class="door-card">'
            f'    <div class="door-eaves"></div>'
            f'    <div class="door-medallion" aria-hidden="true">'
            f'      <div class="med-petal"></div>'
            f'      <div class="med-petal"></div>'
            f'      <div class="med-petal"></div>'
            f'      <div class="med-petal"></div>'
            f'      <div class="med-core"></div>'
            f'    </div>'
            f'    <div class="door-knob left"></div>'
            f'    <div class="door-knob right"></div>'
            f'    <div class="door-hinges left"><span></span><span></span><span></span></div>'
            f'    <div class="door-hinges right"><span></span><span></span><span></span></div>'
            f'    <div class="door-title">{GI["door_title"]}</div>'
            f'    <div class="door-sub">{GI["door_sub"]}</div>',
            unsafe_allow_html=True,
        )
        with st.form("pw_form", clear_on_submit=True):
            pw = st.text_input(
                "password",
                type="password",
                label_visibility="collapsed",
                placeholder="• • • • • •",
                key="pw_input",
            )
            submitted = st.form_submit_button(
                GI["submit_first"] if attempts == 0 else GI["submit_retry"]
            )
        if attempts > 0:
            sw = GI["stamp_words"]
            stamp_word = (
                sw[0] if attempts < 3 else (sw[1] if attempts < 5 else sw[2])
            )
            st.markdown(
                f'<div class="door-err">'
                f'  <span class="door-err-stamp">×{attempts}</span>'
                f'  {GI["door_err_text"]}'
                f'  <span class="door-err-tag">{stamp_word}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('  </div></div>', unsafe_allow_html=True)

    # ── Why + How-to-play (refined: icon 분리 셀, 그라데이션) ──
    try:
        _corpus_n = len(load_corpus())
    except Exception:
        _corpus_n = 120
    try:
        from core.quest import COURSES as _COURSES
        _course_n = len(_COURSES)
    except Exception:
        _course_n = 8
    # ── 1줄 티저 (접힘 상태에서도 가치 노출) — 다국어 ──
    _teaser_html = ''.join(
        f'<span class="teaser-pill">'
        f'{t.format(course_n=_course_n, corpus_n=_corpus_n)}'
        f'</span>'
        for t in GI["teaser"]
    )
    st.markdown(
        f'<div class="gate-teaser">{_teaser_html}</div>',
        unsafe_allow_html=True,
    )

    # ── 정보 구역 단일 expander (4개 섹션 한꺼번에 접고 펴기) ──
    with st.expander(GI["info_expander"], expanded=False):
        # ① 왜 사초 AI?
        st.markdown(
            f'<div class="gate-why">'
            f'  <div class="gate-why-head">'
            f'    <span class="gate-why-title">✨ 왜 사초 AI?</span>'
            f'    <span class="gate-why-sub">범용 AI와 무엇이 다른가</span>'
            f'  </div>'
            f'  <div class="gate-why-grid">'
            f'    <div class="gate-why-cell">'
            f'      <div class="why-icon">🎮</div>'
            f'      <div class="why-body">'
            f'        <b>매번 새 문제</b>'
            f'        <p>AI가 <b>{_corpus_n}건</b> 사료·콘텐츠에서 매번 다르게 출제. 한 번 풀고 끝 X.</p>'
            f'      </div>'
            f'    </div>'
            f'    <div class="gate-why-cell">'
            f'      <div class="why-icon">🗺</div>'
            f'      <div class="why-body">'
            f'        <b>관광지·촬영지까지</b>'
            f'        <p>경복궁 안 7방·경주 첨성대·정동 손탁호텔. 도보 코스 <b>{_course_n}종</b>.</p>'
            f'      </div>'
            f'    </div>'
            f'    <div class="gate-why-cell">'
            f'      <div class="why-icon">🔍</div>'
            f'      <div class="why-body">'
            f'        <b>답변마다 원문 링크</b>'
            f'        <p>조선왕조실록·고려사·한국사DB 1차 사료. 출처 없는 답변 없음.</p>'
            f'      </div>'
            f'    </div>'
            f'    <div class="gate-why-cell">'
            f'      <div class="why-icon">⚖</div>'
            f'      <div class="why-body">'
            f'        <b>학설은 양면</b>'
            f'        <p>갈리는 사안은 양측 견해를 함께. 한·영·일·중 동시.</p>'
            f'      </div>'
            f'    </div>'
            f'  </div>'
            f'  <div class="gate-howto">'
            f'    <b>🎯 노는 법</b>'
            f'    <ol>'
            f'      <li>대문 통과 → 지도에서 가까운 사적 확인</li>'
            f'      <li>코스(정동·경복궁·북촌 등 {_course_n}종) 또는 자유 테마 선택</li>'
            f'      <li>4지선다 + 힌트(-3 사초) → 정답 시 +10~15 사초 (15초 이내 보너스)</li>'
            f'      <li>완주 → 칭호(사관의 으뜸·동무·견습) 획득</li>'
            f'    </ol>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # ② 공공데이터 9종 출처
        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        st.markdown(
            '<h5 class="gate-section-h">📚 어떤 공공데이터로? — 출처 9종 · 라이선스</h5>',
            unsafe_allow_html=True,
        )
        st.markdown(_data_sources_html(), unsafe_allow_html=True)
        # ③ 차별성 매트릭스
        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        st.markdown(
            '<h5 class="gate-section-h">⚔ 범용 AI와 무엇이 다른가 — 4축 비교</h5>',
            unsafe_allow_html=True,
        )
        st.markdown(_diff_matrix_html(_corpus_n), unsafe_allow_html=True)

    # ── 오늘의 한 줄 (랜덤 명언) — 한국어 원문 + 영문 부제 ──
    # 형식: (원문, 출처, 영문 한 줄 부제 — 외국인이 의미 파악)
    quotes = [
        ("이 몸이 죽고 죽어 일백번 고쳐 죽어 …", "정몽주, 단심가",
         "Though this body die and die a hundred times… — Jeong Mong-ju, Song of a Loyal Heart"),
        ("나라가 있으면 무엇이든 할 수 있다", "안중근, 1909 옥중 단상",
         "With a nation, anything is possible. — An Jung-geun, prison reflection, 1909"),
        ("역사가 살아 있으면 나라는 다시 일어난다", "박은식, 한국통사",
         "Where history lives, a nation rises again. — Park Eun-sik, A Painful History of Korea"),
        ("오등은 자에 아 조선의 독립국임을 선언하노라", "기미독립선언서, 1919",
         "We hereby declare Korea an independent nation. — Declaration of Independence, 1919"),
        ("光被四表 化及萬方 — 빛이 사방을 덮고 교화가 만방에 미친다",
         "경복궁 광화문 명문",
         "Light covers the four directions, virtue reaches all lands. "
         "— Inscription, Gwanghwamun Gate, Gyeongbokgung"),
        ("人乃天 — 사람이 곧 하늘이다", "동학, 최제우",
         "Humans are heaven itself. — Donghak, Choe Je-u"),
        ("香遠益淸 — 향기는 멀수록 더 맑다", "경복궁 향원정 명문",
         "The farther the scent, the purer it grows. "
         "— Inscription, Hyangwonjeong Pavilion, Gyeongbokgung"),
        ("나는 이름 없는 사관이외다…", "(소관)",
         "I am but a nameless Sagwan… — The Lesser Recorder"),
        ("勤政 — 부지런히 정사를 돌본다", "경복궁 근정전 명문",
         "Diligence in governance. — Inscription, Geunjeongjeon Throne Hall, Gyeongbokgung"),
    ]
    # 동일 세션 동안 같은 인용 유지 (rerun 시 깜박임 방지)
    if "_gate_quote_idx" not in st.session_state:
        st.session_state._gate_quote_idx = _r.randrange(len(quotes))
    q = quotes[st.session_state._gate_quote_idx % len(quotes)]
    # 영문 부제 — 한국어 모드 사용자에겐 노출 안 함 (이미 원문 이해 가능)
    subtitle_html = (
        f'<div class="gate-quote-gloss">{q[2]}</div>' if glang != "ko" else ''
    )
    st.markdown(
        f'<div class="gate-scroll-wrap">'
        f'  <div class="scroll-rod scroll-rod-top"></div>'
        f'  <div class="gate-quote">'
        f'    <div class="gate-quote-seal">史草</div>'
        f'    <div class="gate-quote-mark">❝</div>'
        f'    <div class="gate-quote-text">{q[0]}</div>'
        f'    {subtitle_html}'
        f'    <div class="gate-quote-who">— {q[1]}</div>'
        f'  </div>'
        f'  <div class="scroll-rod scroll-rod-bottom"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── 사관실 도장 푸터 (한자 史官室은 한·중·일 공통, jade·tag는 i18n) ──
    st.markdown(
        f'<div class="gate-foot">'
        f'  <span class="foot-stamp">史官室</span>'
        f'  <span class="foot-tag">{GI["foot_tag"]}</span>'
        f'  <span class="foot-stamp foot-stamp-jade">{GI["foot_jade"]}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if submitted:
        if pw == expected:
            st.session_state.auth_ok = True
            st.session_state.auth_attempts = 0
            # 게이트에서 선택한 언어를 메인 앱으로 승계 (한 번만 — 사용자가
            # 메인에서 다시 바꿀 수 있음)
            st.session_state.language = glang
            # 다음 게이트 진입 시 새 라인·새 인용 — 갱신
            st.session_state.pop("_gate_line_idx", None)
            st.session_state.pop("_gate_quote_idx", None)
            st.rerun()
        else:
            st.session_state.auth_attempts = attempts + 1
            st.session_state._just_failed = True
            st.rerun()


_pw = _expected_password()
if _pw and not st.session_state.get("auth_ok"):
    render_password_gate(_pw)
    st.stop()


# 여백 데코 캐릭터는 답변 중에도 거슬려서 제거


# ─────────────────────────────────────────────────────────────
# 가로형 톱바
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="topbar-tools">', unsafe_allow_html=True)

bar_cols = st.columns([2.0, 1.2, 1.0, 1.0, 1.0, 0.7, 0.7])

with bar_cols[0]:
    # 빼꼼 캐릭터 — 로고 우상단에서 살짝 보임 (장난스러움 + 귀여움)
    st.markdown(
        f'<a href="?home=1" target="_self" class="topbar-logo-link" '
        f'title="첫 화면으로 돌아가기">'
        f'<div class="topbar-logo">'
        f'<div class="logo-svg">{LOGO_SVG}</div>'
        f'<div class="topbar-text-wrap">'
        f'  <div class="brand">사초(史草) AI</div>'
        f'  <div class="brand-sub">— 졸린 사관과 함께 —</div>'
        f'</div>'
        f'<div class="topbar-peek">{char_img("peeking", width=42)}</div>'
        f'</div>'
        f'</a>',
        unsafe_allow_html=True,
    )

with bar_cols[1]:
    # 게임 모드 토글 (퀘스트 ↔ 자유 대화)
    view_options = {
        T["mode_quest"]: "quest",
        T["mode_chat"]:  "chat",
    }
    inv_v = {v: k for k, v in view_options.items()}
    current_view = "chat" if st.session_state.view == "chat" else "quest"
    new_view_label = st.selectbox(
        "view",
        list(view_options.keys()),
        index=list(view_options.keys()).index(inv_v.get(current_view, T["mode_quest"])),
        label_visibility="collapsed",
        key="view_select",
    )
    new_view = view_options[new_view_label]
    if new_view != st.session_state.view and st.session_state.view != "collection":
        st.session_state.view = new_view
        st.rerun()

with bar_cols[2]:
    lang_options = {"한국어": "ko", "English": "en", "日本語": "ja", "中文 (简体)": "zh"}
    inv = {v: k for k, v in lang_options.items()}
    lang_label = st.selectbox(
        "language",
        list(lang_options.keys()),
        index=list(lang_options.keys()).index(inv[st.session_state.language]),
        label_visibility="collapsed",
        key="lang_select",
    )
    if lang_options[lang_label] != st.session_state.language:
        # 언어만 바뀌었을 뿐, 대화·퀘스트 진행은 보존 (어차피 다음 답변부터 새 언어 적용)
        st.session_state.language = lang_options[lang_label]
        st.rerun()

with bar_cols[3]:
    mode_options = ["일반", "가족 (만 8세+)"]
    cur = mode_options.index(st.session_state.mode) if st.session_state.mode in mode_options else 0
    new_mode = st.selectbox(
        "mode",
        mode_options,
        index=cur,
        label_visibility="collapsed",
        key="mode_select",
    )
    st.session_state.mode = new_mode

with bar_cols[4]:
    n_seen = len(st.session_state.collection)
    label = f"{T['collection_btn']} ({n_seen})" if n_seen else T["collection_btn"]
    is_in_collection = st.session_state.view == "collection"
    if st.button(label, key="btn_collection", use_container_width=True,
                 help="내가 마주한 사료 모음"):
        st.session_state.view = "quest" if is_in_collection else "collection"
        st.rerun()

with bar_cols[5]:
    with st.popover("⚙", use_container_width=True):
        st.markdown("**시연 옵션**")
        st.session_state.show_rag_debug = st.toggle(
            "사관의 검색 메모 보기",
            value=st.session_state.show_rag_debug,
        )
        st.session_state.show_map = st.toggle(
            "사료 위치 지도 보기",
            value=st.session_state.show_map,
        )
        st.markdown("---")
        # ── 데이터·차별성 패널 (로그인 후에도 검토 가능) ──
        try:
            _corpus_n_pop = len(load_corpus())
        except Exception:
            _corpus_n_pop = 0
        with st.expander("📚 공공데이터 출처 9종", expanded=False):
            st.markdown(_data_sources_html(), unsafe_allow_html=True)
        with st.expander("⚔ 범용 AI 대비 차별성", expanded=False):
            st.markdown(_diff_matrix_html(_corpus_n_pop),
                        unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(
            f"**API 키**: {'✨ 깨어 있음' if api_key_present else '💤 잠들어 있음'}"
        )
        if st.session_state.messages:
            export_payload = {
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "language": st.session_state.language,
                "mode": st.session_state.mode,
                "messages": [
                    {
                        "role": m["role"],
                        "content": m["content"],
                        "badge": m.get("badge"),
                        "source_ids": m.get("source_ids", []),
                        "usage": m.get("usage"),
                    }
                    for m in st.session_state.messages
                ],
            }
            st.download_button(
                label=T["export_label"],
                data=json.dumps(export_payload, ensure_ascii=False, indent=2),
                file_name=f"sagwan_chat_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

with bar_cols[6]:
    if st.button("🔄", help=T["reset_label"], use_container_width=True):
        st.session_state.messages = []
        st.session_state.collection = {}
        st.session_state.view = "quest"
        st.session_state.current_q = None
        st.session_state.q_answered = False
        st.session_state.credits = 0
        st.session_state.streak = 0
        st.session_state.total_attempts = 0
        st.session_state.total_correct = 0
        st.session_state.q_seen_ids = []
        # 코스 진행 + 부수 상태 초기화 (이전엔 누락돼 중간에 🔄 누르면 어색)
        st.session_state.course_idx = 0
        st.session_state.course_score = 0
        st.session_state.course_finished = False
        st.session_state.eliminated_options = []
        st.session_state.qtypes_per_card = {}
        # 랜딩 지도 표시 모드도 기본값 복귀 (크게 보기로 둔 채 리셋하면 어색)
        st.session_state.landing_map_collapsed = False
        st.session_state.landing_map_expanded = False
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 헤더 (큰 사관 + 말풍선 타이틀 + 빼꼼 캐릭터)
# ─────────────────────────────────────────────────────────────
HEADER_TEXT = {
    "ko": ("사관(史官)과 두런두런",
           "고조선부터 광복까지 — 답변마다 1차 사료 링크. 학설이 갈리면 양측 견해를 함께."),
    "en": ("Chatting with the Sleepy Sagwan",
           "Gojoseon to the 1945 Liberation — every reply links to a primary Korean record, with multiple scholarly views where they exist."),
    "ja": ("ねむたい史官とぽつぽつ",
           "古朝鮮から光復まで — 答えごとに原典リンク。学説が分かれる事案は両論併記。"),
    "zh": ("和犯困的史官闲谈",
           "从古朝鲜到光复 — 每条答复附原典链接,学界争议则并列双方观点。"),
}
# Hero 헤더 — 자유 대화(chat) 뷰에서만 노출.
# hero_scene.png 있으면 wide banner mode / 없으면 char-row hero 폴백
if st.session_state.view == "chat":
    title, subtitle = HEADER_TEXT[st.session_state.language]
    from pathlib import Path as _PathHero
    _hero_path = _PathHero(__file__).parent / "assets" / "hero_scene.png"
    if _hero_path.exists():
        # 전용 wide banner — 사관 책상 일러스트
        import base64 as _b64hero
        _hero_b64 = _b64hero.b64encode(_hero_path.read_bytes()).decode("ascii")
        st.markdown(
            f'<div class="hero hero-scene-mode">'
            f'  <div class="hero-banner">'
            f'    <img src="data:image/png;base64,{_hero_b64}" '
            f'         alt="사관의 책상" />'
            f'  </div>'
            f'  <div class="hero-text">'
            f'    <h1>📜 {title}</h1>'
            f'    <p>{subtitle}</p>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        # Fallback — 기존 캐릭터-row hero
        st.markdown(
            f'<div class="hero">'
            f'  <div class="hero-char">{char_img("cheek", width=170)}</div>'
            f'  <div class="hero-text">'
            f'    <h1>📜 {title}</h1>'
            f'    <p>{subtitle}</p>'
            f'  </div>'
            f'  <div class="hero-peek">{char_img("hmm", width=110)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────
# 뷰 분기 — 사료 보관함이면 본 페이지에서 종료 (헤더는 위에서 이미 그려졌음)
# ─────────────────────────────────────────────────────────────
def _source_authority(url: str) -> str:
    """URL에서 출처 기관을 식별해 사용자에게 신뢰도 라벨로 노출."""
    if not url:
        return "참고 자료"
    if "sillok.history.go.kr" in url:
        return "🏛 조선왕조실록 (국사편찬위원회)"
    if "sjw.history.go.kr" in url:
        return "🏛 승정원일기 (국사편찬위원회)"
    if "db.history.go.kr" in url:
        return "🏛 한국사데이터베이스 (국사편찬위원회)"
    if "itkc.or.kr" in url:
        return "🏛 한국고전번역원"
    if "royalpalace.go.kr" in url or "cha.go.kr" in url or "cdg.go.kr" in url:
        return "🏛 문화재청·궁능유적본부"
    if "go.kr" in url:
        return "🏛 정부·공공기관"
    if "or.kr" in url:
        return "📚 비영리·학술기관"
    return "📚 참고 자료"


def _place_links(c: SourceCard) -> str:
    """장소 좌표 + 제목으로 지도·사진·카카오·관광공사(다국어) 링크 생성."""
    import urllib.parse as up
    bits = []
    title_raw = c.title.split("—")[0].strip()
    place_raw = c.place.split("(")[0].strip()
    title_q = up.quote(title_raw)
    place_q = up.quote(place_raw)
    has_coords = bool(c.place_coords) and len(c.place_coords) == 2

    # 1) 카카오맵 — 한국 관광지엔 가장 정확 (좌표 + 제목 deep link)
    if has_coords:
        lon, lat = c.place_coords
        # KakaoMap Link API: /link/map/{name},{lat},{lng}
        kakao_url = f"https://map.kakao.com/link/map/{title_q},{lat},{lon}"
        bits.append(
            f'<a class="place-link kakao-link" href="{kakao_url}" target="_blank" '
            f'rel="noopener" title="카카오맵에서 위치 확인">'
            f'{T["kakao_map"]}</a>'
        )
        # 2) 거리뷰(로드뷰) — 네이버 파노라마 (Kakao 의 urlX/urlY 는 KATEC
        # 좌표계라 WGS84 위경도가 자동 변환되지 않음. 네이버는 c={lng},{lat}
        # 에 ,dh suffix 로 거리뷰 패널을 안정적으로 띄움)
        naver_pano = (
            f"https://map.naver.com/v5/?c={lon},{lat},17,0,0,0,dh"
        )
        bits.append(
            f'<a class="place-link roadview-link" href="{naver_pano}" target="_blank" '
            f'rel="noopener" '
            f'title="네이버 거리뷰로 현장 360° 파노라마 진입 — 카카오맵 화면에서도 「로드뷰」 버튼으로 가능">'
            f'{T["kakao_roadview"]}</a>'
        )

    # 3) Google Maps — 다국어 사용자 / 좌표 없으면 검색
    if has_coords:
        lon, lat = c.place_coords
        gmap = f"https://www.google.com/maps?q={lat},{lon}({title_q})"
    else:
        gmap = f"https://www.google.com/maps/search/{title_q}"
    bits.append(
        f'<a class="place-link" href="{gmap}" target="_blank" rel="noopener">'
        f'{T["map_open"]}</a>'
    )

    # 4) 사진 검색 — 한국어는 네이버, 외국어는 Google 이미지
    lang = st.session_state.language
    if lang == "ko":
        img = f"https://search.naver.com/search.naver?where=image&query={place_q}"
    else:
        img = f"https://www.google.com/search?tbm=isch&q={place_q}"
    bits.append(
        f'<a class="place-link" href="{img}" target="_blank" rel="noopener">'
        f'{T["photo_search"]}</a>'
    )

    # 3) 한국관광공사 Visit Korea — 다국어 (TourAPI 4.0 데이터 기반 공식 안내)
    visit_domain = {
        "ko": "korean.visitkorea.or.kr",
        "en": "english.visitkorea.or.kr",
        "ja": "japanese.visitkorea.or.kr",
        "zh": "chinese.visitkorea.or.kr",
    }.get(lang, "english.visitkorea.or.kr")
    visit_url = (
        f"https://{visit_domain}/search/search_list.do?keyword={place_q}"
    )
    bits.append(
        f'<a class="place-link" href="{visit_url}" target="_blank" rel="noopener" '
        f'title="한국관광공사 — TourAPI 4.0 기반 공식 안내">'
        f'{T["tour_info"]}</a>'
    )

    # 4) KTO Odii 오디오가이드 — 다국어 (관광 명소 한정, 추상 entry는 제외)
    abstract = any(s in (c.place or "").lower()
                   for s in ["전국", "한국 무속", "전통 사후세계", "조선 전체"])
    if not abstract:
        odii_url = f"https://www.odii.or.kr/search/main?keyword={place_q}"
        bits.append(
            f'<a class="place-link" href="{odii_url}" target="_blank" rel="noopener" '
            f'title="문화체육관광부·한국관광공사 무료 다국어 오디오가이드">'
            f'{T["audio_guide"]}</a>'
        )

    return " ".join(bits)


def _special_dataset_chip(c: SourceCard) -> str:
    """공모전 특별제공 데이터셋(한복·국악·문양) 활용 카드 칩.

    우선순위: ``c.dataset_tags`` 명시 → 본문 키워드 폴백.
    """
    explicit = set(getattr(c, "dataset_tags", []) or [])
    chips: list[str] = []

    if explicit:
        if "hanbok" in explicit:
            chips.append(
                '<span class="dataset-chip" '
                'title="공모전 특별제공: 한국공예·디자인문화진흥원 한복 데이터셋">'
                '👘 한복 데이터셋</span>'
            )
        if "gugak" in explicit:
            chips.append(
                '<span class="dataset-chip" '
                'title="공모전 특별제공: 국립국악원 자료">'
                '🎶 국악 데이터셋</span>'
            )
        if "pattern" in explicit:
            chips.append(
                '<span class="dataset-chip" '
                'title="공모전 특별제공: 전통문양 데이터셋">'
                '🌀 전통문양 데이터셋</span>'
            )
        return ' '.join(chips)

    # 폴백 — 키워드 기반 추측 (정확도 낮음)
    text = " ".join([c.title or "", c.summary or "",
                     " ".join(c.tags or []), c.id or ""])
    if c.id.startswith("kculture-") or any(
        k in text for k in ["한복", "곤룡포", "단령", "철릭", "장신구",
                              "갓", "비녀", "당의"]
    ):
        chips.append(
            '<span class="dataset-chip" '
            'title="공모전 특별제공: 한국공예·디자인문화진흥원 한복·전통문양 (추정)">'
            '👘 한복·문양 데이터셋</span>'
        )
    if any(k in text for k in ["국악", "판소리", "민요", "장단", "굿거리",
                                 "사물놀이", "아악", "정악", "종묘제례악"]):
        chips.append(
            '<span class="dataset-chip" '
            'title="공모전 특별제공: 국립국악원 자료 (추정)">'
            '🎶 국악 데이터셋</span>'
        )
    if any(k in text for k in ["문양", "단청", "기와", "전통 문양", "오방색"]):
        chips.append(
            '<span class="dataset-chip" '
            'title="공모전 특별제공: 전통문양 데이터셋 (추정)">'
            '🌀 전통문양</span>'
        )
    return ' '.join(chips)


def _nearby_tour_chip(c: SourceCard) -> str:
    """TourAPI 4.0 enrichment 결과 — 주변 KTO 등재 명소 N곳 칩."""
    side = getattr(c, "tour_nearby", None)
    if not side:
        return ''
    spots = side.get("spots") or []
    if not spots:
        return ''
    radius = side.get("radius_m", 500)
    top = spots[:3]
    names = " · ".join(s["title"] for s in top)
    tip = (
        f"한국관광공사 TourAPI 4.0 · 반경 {radius}m: {names}"
        + (f" 외 {len(spots) - 3}곳" if len(spots) > 3 else "")
    )
    return (
        f'<span class="dataset-chip nearby-chip" title="{tip}">'
        f'🏞 주변 명소 {len(spots)}곳 · TourAPI</span>'
    )


def render_evidence_cards(cards: list[SourceCard]) -> None:
    if not cards:
        return
    st.markdown(f"##### {T['evidence_header']}")
    for c in cards:
        authority = _source_authority(c.source_url)
        chip_html = " ".join(
            x for x in [_special_dataset_chip(c), _nearby_tour_chip(c)] if x
        )
        special_html = (
            f'<div class="dataset-chips">{chip_html}</div>' if chip_html else ''
        )
        # 원문 발췌 + 라이선스는 기본 접힘 (정보 과부하 감소).
        # HTML <details> 사용 — Streamlit rerun 없이 클라이언트 토글.
        st.markdown(
            f'<div class="evidence-card">'
            f'<h4>📜 {T["evidence_id"]} <code>{c.id}</code> · {c.title}</h4>'
            f'<div class="meta">📅 {c.date} &nbsp;|&nbsp; 📍 {c.place} '
            f'&nbsp;|&nbsp; 📖 {c.source}</div>'
            f'{special_html}'
            f'<div class="body">{c.summary}</div>'
            f'<details class="evidence-details">'
            f'  <summary>📖 원문 발췌 · 라이선스 보기</summary>'
            f'  <div class="body" style="margin-top:8px;color:#5C4A33;font-size:13px;">'
            f'    <b>{T["original_excerpt"]}</b>: <em>{c.original_text}</em>'
            f'  </div>'
            f'  <div class="license-tag">📄 {c.license}</div>'
            f'</details>'
            f'<div class="place-row">{_place_links(c)}</div>'
            f'<div class="verify-row">'
            f'<a class="verify-btn" href="{c.source_url}" target="_blank" '
            f'rel="noopener">🔍 {T["view_source"]}</a>'
            f'<span class="source-authority">{authority}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_evidence_map(cards: list[SourceCard]) -> None:
    if not st.session_state.show_map or not cards:
        return
    rows = [
        {"lat": c.place_coords[1], "lon": c.place_coords[0]}
        for c in cards if c.place_coords and len(c.place_coords) == 2
    ]
    if not rows:
        return
    st.markdown(f"##### {T['map_title']}")
    st.map(pd.DataFrame(rows), size=40, zoom=14)


def _site_category(card: SourceCard) -> tuple[str, str, str]:
    """카테고리 식별 — (이모지 아이콘, 색, 라벨). 마커 색상으로도 구분."""
    text = " ".join([card.title, card.place, " ".join(card.tags), card.id])

    if card.id.startswith("kculture-"):
        return "🎬", "#C97064", "K-콘텐츠"
    if card.id.startswith("gbg-"):
        return "🏯", "#8C5A2E", "경복궁 내"
    if card.id.startswith("dsg-"):
        return "🏛", "#B8763C", "덕수궁 내"
    if any(k in text for k in ["임진왜란", "한산", "명량", "병자호란", "삼전도",
                                 "진주성", "남한산성", "위화도"]):
        return "⚔", "#5B4438", "전적지"
    if any(k in text for k in ["불국사", "석굴암", "첨성대", "안압지", "월지",
                                 "정림사", "무령왕릉", "종묘", "도담삼봉", "사인암"]):
        return "🗿", "#7A6240", "유적·유물"
    if any(k in text for k in ["3.1운동", "안중근", "윤봉길", "유관순", "임시정부",
                                 "광복", "독립", "의병", "광주학생", "광복군",
                                 "신간회", "의열단", "이회영", "한일강제병합", "한국전쟁",
                                 "을사늑약", "을미사변", "아관파천"]):
        return "🇰🇷", "#A04030", "독립·근대"
    if any(k in text for k in ["경복궁", "창덕궁", "창경궁", "덕수궁", "경운궁",
                                 "수원화성", "경기전", "오죽헌", "도산서원", "하회"]):
        return "🏯", "#8C1D18", "궁궐·서원"
    if any(k in text for k in ["단양", "강릉", "안동", "전주", "공주", "부여", "경주",
                                 "정동", "관광지"]):
        return "🏞", "#5A7A3B", "자연·관광"
    return "📜", "#A8554A", "사료"


_LANDING_LEGEND = [
    ("🏯", "궁궐·서원"),
    ("🏛", "궁궐 내부"),
    ("🗿", "유적·유물"),
    ("⚔",  "전적지"),
    ("🇰🇷", "독립·근대"),
    ("🏞", "자연·관광"),
    ("🎬", "K-콘텐츠"),
    ("📜", "사료"),
    ("👤", "내 위치"),
]


def render_landing_map() -> None:
    """게임 진입 화면 상단 — 모든 게임 장소를 카테고리별 아이콘으로 표시.
    사용자 위치가 있으면 함께 표시. 클릭 시 popup 으로 장소 안내.
    """
    if not st.session_state.show_map:
        return

    corpus = load_corpus()
    # 좌표가 있는 entry만 (K-콘텐츠 추상 entry 일부는 제외)
    valid = []
    for c in corpus:
        if not c.place_coords or len(c.place_coords) != 2:
            continue
        # 의미 없는 일반/전국 위치는 스킵
        place_lower = c.place.lower()
        if any(s in place_lower for s in ["전국", "한국 무속", "전통 사후세계"]):
            continue
        valid.append(c)

    user_loc = st.session_state.user_geo
    # landing_map_collapsed / landing_map_expanded 는 init_state 에서 초기화됨

    # 헤더 + 위치 요청 (한 줄, 명확히 노출) — 우측에 접기/크게보기 토글 2개
    user_loc_status = (
        f'✅ {user_loc[0]:.4f}, {user_loc[1]:.4f}' if user_loc else '미설정'
    )
    head_col_l, head_col_m, head_col_r = st.columns([5, 1, 1])
    with head_col_l:
        st.markdown(
            '<div class="landing-map-head">'
            '  <div>'
            '    <h5 style="margin:0;border:none;">'
            '      🗺 어디서 놀까요? — <span style="color:#A8554A;font-weight:700;">'
            f'      게임 장소 {len(valid)}곳</span>'
            '    </h5>'
            '    <span class="landing-map-sub">'
            '      핀을 누르면 장소 안내, 모드를 골라 시작하시면 됩니다'
            '    </span>'
            '  </div>'
            '  <div class="landing-map-geo">'
            f'    <span class="geo-status">📍 내 위치: <b>{user_loc_status}</b></span>'
            '  </div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with head_col_m:
        # 크게 보기 토글 — 지도 height 340 → 720, 줌·팬 여유
        expand_label = (
            "🔍 보통" if st.session_state.landing_map_expanded else "🔍 크게"
        )
        if st.button(expand_label, key="landing_map_expand_toggle",
                     use_container_width=True,
                     help="지도를 크게 펼쳐 자유롭게 줌·이동"):
            st.session_state.landing_map_expanded = \
                not st.session_state.landing_map_expanded
            # 크게 보기로 전환하면 접힘은 해제
            if st.session_state.landing_map_expanded:
                st.session_state.landing_map_collapsed = False
            st.rerun()
    with head_col_r:
        toggle_label = (
            "🗺 펼치기" if st.session_state.landing_map_collapsed else "🗺 접기"
        )
        if st.button(toggle_label, key="landing_map_toggle",
                     use_container_width=True,
                     help="지도를 접으면 모드 선택까지 빠르게 이동"):
            st.session_state.landing_map_collapsed = \
                not st.session_state.landing_map_collapsed
            st.rerun()

    if st.session_state.landing_map_collapsed:
        # 접힘 — 얇은 안내 바만 표시 (folium 로딩 스킵 → 가벼움)
        st.markdown(
            '<div class="landing-map-collapsed-hint">'
            '  🗺 지도 접힘 — 우측 "펼치기"를 누르면 다시 표시. '
            '  바로 아래 모드 선택으로 시작하실 수 있소이다.'
            '</div>',
            unsafe_allow_html=True,
        )
        return
    # 위치 권한 버튼 — expander 안에 숨기지 않고 헤더 옆에 노출 (한 번이면 끝)
    if not user_loc:
        try:
            from streamlit_geolocation import streamlit_geolocation
            geo_l, geo_r = st.columns([1, 5])
            with geo_l:
                _loc = streamlit_geolocation()
            with geo_r:
                st.markdown(
                    '<div class="geo-hint">← 좌측 버튼을 누르면 '
                    '<b>내 위치를 지도에 표시</b>하고, 가까운 사적부터 '
                    '문제를 받을 수 있소이다 (브라우저 권한 허용).</div>',
                    unsafe_allow_html=True,
                )
            if _loc and _loc.get("latitude") is not None:
                st.session_state.user_geo = (
                    float(_loc["latitude"]), float(_loc["longitude"])
                )
                st.rerun()
        except ImportError:
            st.info("위치 라이브러리 미설치 — requirements 재배포 필요.")

    try:
        import folium
        from streamlit_folium import st_folium

        # 중심: 사용자 위치 우선, 없으면 광화문 (초기 마운트 1회만)
        # NOTE: 이전엔 returned_objects=[center,zoom] 으로 매 pan/zoom rerun → Map
        # 객체가 새 location 으로 재생성되며 사용자 줌·팬을 덮어쓰는 버그가 있었다.
        # key + returned_objects=[] 조합으로 컴포넌트 내부가 줌·팬 보존하도록 변경.
        if user_loc:
            center = list(user_loc)
            zoom = 14
        else:
            center = [37.5759, 126.9769]  # 광화문
            zoom = 11

        m = folium.Map(
            location=center, zoom_start=zoom,
            tiles="OpenStreetMap",
        )

        for c in valid:
            icon, color, label = _site_category(c)
            popup_html = (
                f'<div style="font-family:serif;font-size:13px;width:240px;">'
                f'<div style="font-weight:700;color:{color};margin-bottom:4px;">'
                f'{icon} {c.title}</div>'
                f'<div style="color:#666;font-size:11.5px;margin-bottom:3px;">'
                f'📍 {c.place}</div>'
                f'<div style="color:#888;font-size:11px;font-style:italic;">'
                f'{label} · {c.era}</div>'
                f'</div>'
            )
            folium.Marker(
                [c.place_coords[1], c.place_coords[0]],
                tooltip=f"{icon} {c.title}",
                popup=folium.Popup(popup_html, max_width=280),
                icon=folium.DivIcon(
                    html=(
                        f'<div style="font-size:22px;'
                        f'text-shadow:0 0 3px white, 0 0 5px white;">'
                        f'{icon}</div>'
                    ),
                    icon_size=(30, 30),
                    icon_anchor=(15, 15),
                ),
            ).add_to(m)

        if user_loc:
            folium.Marker(
                list(user_loc),
                tooltip="📍 내 위치",
                icon=folium.DivIcon(
                    html=(
                        '<div style="font-size:32px;'
                        'text-shadow:0 0 4px white, 0 0 8px white;">👤</div>'
                    ),
                    icon_size=(40, 40),
                    icon_anchor=(20, 32),
                ),
            ).add_to(m)
            # 반경 5km 원 (가까운 사적 시각화)
            folium.Circle(
                list(user_loc),
                radius=5000,
                color="#2E6418",
                weight=2,
                opacity=0.45,
                fill=True,
                fill_opacity=0.06,
            ).add_to(m)

        # 크게 보기 시 720 / 보통 340 / 모바일 CSS 추가 압축
        # key 만 사용 — 컴포넌트 내부가 줌·팬 보존, rerun 미트리거
        _map_h = 720 if st.session_state.get("landing_map_expanded") else 340
        _map_cls = (
            "landing-map-folium expanded"
            if st.session_state.get("landing_map_expanded")
            else "landing-map-folium"
        )
        # key 에 expanded 상태 포함 → 모드 전환 시 컴포넌트 새로 마운트되며 height 적용
        _map_key = (
            "landing_map_v2_big"
            if st.session_state.get("landing_map_expanded")
            else "landing_map_v2"
        )
        st.markdown(f'<div class="{_map_cls}">', unsafe_allow_html=True)
        st_folium(
            m, width=None, height=_map_h,
            key=_map_key,
            returned_objects=[],
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # 범례 (legend)
        legend_html = '<div class="map-legend">'
        for icon, label in _LANDING_LEGEND:
            legend_html += f'<span><b>{icon}</b> {label}</span>'
        legend_html += '</div>'
        st.markdown(legend_html, unsafe_allow_html=True)

        # (위치 권한 버튼은 헤더로 승격됨 — 중복 노출 제거)
        return
    except ImportError:
        # 폴백: st.map (아이콘은 안 됨, 색상으로만)
        rows = []
        for c in valid:
            _, color, _ = _site_category(c)
            rows.append({
                "lat": c.place_coords[1],
                "lon": c.place_coords[0],
                "color": color,
                "size": 60,
            })
        if user_loc:
            rows.append({
                "lat": user_loc[0], "lon": user_loc[1],
                "color": "#2E6418", "size": 150,
            })
        if rows:
            st.map(pd.DataFrame(rows), size="size", color="color")


def render_course_map(course_id: str, current_idx: int,
                       user_loc: tuple[float, float] | None = None) -> None:
    """코스 모드 — Folium 지도에 모든 단서 마커 + 사용자 위치 표시.

    각 단서는 사관·두루마리 아이콘으로 표시 (📜 = 다음·🏛 = 지나온·👤 = 본인)
    """
    if not st.session_state.show_map:
        return
    from core.quest import COURSES
    course = COURSES.get(course_id)
    if not course:
        return

    corpus = load_corpus()
    cards = []
    for i, cid in enumerate(course["card_ids"]):
        card = next((c for c in corpus if c.id == cid), None)
        if card and card.place_coords and len(card.place_coords) == 2:
            cards.append((i, card))
    if not cards:
        return

    # Folium 사용 가능하면 풀 기능, 아니면 st.map 폴백
    try:
        import folium
        from streamlit_folium import st_folium

        # 중심 좌표 — 모든 단서의 평균.
        # 단서 인덱스가 바뀌면 컴포넌트 key 도 바뀌어 자동 재중앙화.
        avg_lat = sum(c.place_coords[1] for _, c in cards) / len(cards)
        avg_lon = sum(c.place_coords[0] for _, c in cards) / len(cards)
        course_zoom = 17

        st.markdown(
            "##### 🗺 코스 지도 — "
            "<span style='color:#C97064'>📜 현재</span> · "
            "<span style='color:#5C4A38'>🏛 지나온 곳</span> · "
            "<span style='color:#9A958C'>두루마리 다음</span>"
            + (" · <span style='color:#2E6418'>👤 내 위치</span>" if user_loc else ""),
            unsafe_allow_html=True,
        )

        m = folium.Map(
            location=[avg_lat, avg_lon], zoom_start=course_zoom,
            tiles="OpenStreetMap",
        )

        # 단서 마커
        for i, card in cards:
            is_current = (i == current_idx)
            is_done = (i < current_idx)
            if is_current:
                icon_html = '<div style="font-size:28px;">📜</div>'
                color = "#C97064"
            elif is_done:
                icon_html = '<div style="font-size:22px;opacity:0.7;">🏛</div>'
                color = "#5C4A38"
            else:
                icon_html = '<div style="font-size:22px;opacity:0.5;">📜</div>'
                color = "#9A958C"
            popup_html = (
                f'<div style="font-family:serif;font-size:13px;width:200px;">'
                f'<b>{i+1}. {card.title}</b><br>'
                f'<span style="color:#666;font-size:11.5px;">📍 {card.place}</span>'
                f'</div>'
            )
            folium.Marker(
                [card.place_coords[1], card.place_coords[0]],
                tooltip=f"{i+1}. {card.title}",
                popup=folium.Popup(popup_html, max_width=240),
                icon=folium.DivIcon(html=icon_html, icon_size=(36, 36),
                                    icon_anchor=(18, 18)),
            ).add_to(m)

        # 사용자 위치 (있으면)
        if user_loc:
            folium.Marker(
                list(user_loc),
                tooltip="내 위치",
                icon=folium.DivIcon(
                    html='<div style="font-size:30px;">👤</div>',
                    icon_size=(36, 36), icon_anchor=(18, 30),
                ),
            ).add_to(m)
            # 사용자 → 현재 단서 연결선
            cur_card = next((c for i, c in cards if i == current_idx), None)
            if cur_card:
                folium.PolyLine(
                    locations=[
                        list(user_loc),
                        [cur_card.place_coords[1], cur_card.place_coords[0]],
                    ],
                    color="#2E6418", weight=3, opacity=0.6, dash_array="6",
                ).add_to(m)

        # key 에 단서 인덱스 포함 → 단서 바뀌면 자동 재중앙화, 같은 단서 안에서는
        # 사용자 줌·팬 보존. returned_objects=[] 로 rerun 미트리거.
        st_folium(
            m, width=None, height=360,
            key=f"course_map_v2_{course_id}_{current_idx}",
            returned_objects=[],
        )
        return
    except ImportError:
        pass

    # 폴백: st.map
    rows = []
    for i, card in cards:
        rows.append({
            "lat": card.place_coords[1],
            "lon": card.place_coords[0],
            "size": 220 if i == current_idx else (90 if i < current_idx else 70),
            "color": "#C97064" if i == current_idx else ("#5C4A38" if i < current_idx else "#BFBAB1"),
        })
    if user_loc:
        rows.append({"lat": user_loc[0], "lon": user_loc[1],
                     "size": 180, "color": "#2E6418"})
    st.markdown("##### 🗺 코스 지도")
    st.map(pd.DataFrame(rows), size="size", color="color")


def render_collection_page() -> None:
    """사관과 함께 본 사료 보관함."""
    cards = list(st.session_state.collection.values())
    n = len(cards)

    if n == 0:
        st.markdown(
            f'<div class="collection-empty">'
            f'  <div class="collection-empty-char">{char_img("facedown", width=160)}</div>'
            f'  <div class="collection-empty-text">'
            f'    <h3>{T["collection_empty"]}</h3>'
            f'    <p>{T["collection_empty_hint"]}</p>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button(T["back_to_chat"], key="back_chat_empty"):
            st.session_state.view = "chat"
            st.rerun()
        return

    st.markdown(
        f'<div class="collection-header">'
        f'  <div class="collection-char">{char_img("reading", width=110)}</div>'
        f'  <div class="collection-head-text">'
        f'    <h3>📜 {T["collection_title"]}</h3>'
        f'    <p>{T["collection_sub"]} <b>{n}</b>{T["collection_count"]}.</p>'
        f'  </div>'
        f'  <div class="collection-char-side">{char_img("books", width=90)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── 필터 + 정렬 (수집한 카드가 늘어도 잘 찾도록) ──
    # 카테고리 = _site_category 의 (icon, color, label) — UI 라벨에 icon + count 포함
    def _era_label(card: SourceCard) -> str:
        _, _, lab = _site_category(card)
        return lab
    def _era_icon(label: str) -> str:
        # _site_category 매핑을 역으로 — 첫 카드 기준
        for c in cards:
            ic, _, lb = _site_category(c)
            if lb == label:
                return ic
        return "📂"

    # 동적 era 옵션 — 카운트 포함, 카운트 많은 순 정렬
    from collections import Counter as _Counter
    _era_counts = _Counter(_era_label(c) for c in cards)
    era_keys_sorted = [lab for lab, _ in _era_counts.most_common()]
    # display label → 실제 매칭 label 매핑
    era_display: dict[str, str] = {f"📂 전체 ({n})": "전체"}
    for lab in era_keys_sorted:
        n = _era_counts[lab]
        era_display[f"{_era_icon(lab)} {lab} ({n})"] = lab

    f_cols = st.columns([2, 2, 3])
    with f_cols[0]:
        era_display_key = st.selectbox(
            "📂 분류 필터",
            list(era_display.keys()),
            index=0,
            key="col_filter_era",
        )
        era_pick = era_display[era_display_key]
    with f_cols[1]:
        sort_options = {
            "📅 시대순 (오래된 먼저)": "date_asc",
            "📅 시대순 (최근 먼저)": "date_desc",
            "🔤 제목순": "title",
            "📍 장소순": "place",
        }
        sort_pick_label = st.selectbox(
            "↕ 정렬",
            list(sort_options.keys()),
            index=0,
            key="col_filter_sort",
        )
        sort_key = sort_options[sort_pick_label]
    with f_cols[2]:
        q_search = st.text_input(
            "🔍 제목·장소·인물 키워드",
            value="",
            placeholder="예: 광해군 · 경복궁 · 안중근",
            key="col_filter_q",
            label_visibility="visible",
        )

    # 필터 적용
    filtered = list(cards)
    if era_pick != "전체":
        filtered = [c for c in filtered if _era_label(c) == era_pick]
    if q_search.strip():
        qlow = q_search.strip().lower()
        filtered = [
            c for c in filtered
            if qlow in c.title.lower()
            or qlow in c.place.lower()
            or any(qlow in p.lower() for p in (c.related_persons or []))
            or any(qlow in t.lower() for t in (c.tags or []))
        ]
    # 견고한 시대순 정렬 — 카드별 date 포맷이 혼합 (YYYY-MM-DD / "1410 (정종)"
    # / "1395 / 1865" / "-2333-10-03" BC)이라 문자열 정렬은 어긋남.
    # 선행 (음수 가능) 정수만 추출해 1차 키로 사용, 동률은 원문으로 2차.
    import re as _re_sort
    def _date_key(card: SourceCard) -> tuple[int, str]:
        m = _re_sort.match(r'-?\d+', card.date or "")
        return (int(m.group()) if m else 99999, card.date or "")
    if sort_key == "date_asc":
        filtered.sort(key=_date_key)
    elif sort_key == "date_desc":
        filtered.sort(key=_date_key, reverse=True)
    elif sort_key == "title":
        filtered.sort(key=lambda x: x.title)
    elif sort_key == "place":
        filtered.sort(key=lambda x: x.place)

    st.caption(
        f"📂 {era_pick} · 정렬 {sort_pick_label} · 결과 "
        f"<b>{len(filtered)}</b>/{n}건"
    )

    if not filtered:
        st.info("🔎 검색 결과가 없소이다. 필터를 풀거나 다른 키워드로 시도해 보시오.")
        if st.button("필터 초기화", key="col_clear_filter"):
            for k in ("col_filter_era", "col_filter_sort", "col_filter_q"):
                st.session_state.pop(k, None)
            st.rerun()
    else:
        # 2-column 그리드 (좁은 화면에서는 자동 1단)
        cols = st.columns(2)
        for i, c in enumerate(filtered):
            with cols[i % 2]:
                st.markdown(
                    f'<div class="evidence-card">'
                    f'<h4>📜 {T["evidence_id"]} {c.id} · {c.title}</h4>'
                    f'<div class="meta">📅 {c.date} &nbsp;|&nbsp; 📍 {c.place} '
                    f'&nbsp;|&nbsp; 📖 {c.source}</div>'
                    f'<div class="body">{c.summary}</div>'
                    f'<details class="evidence-details">'
                    f'  <summary>📖 원문 발췌 · 라이선스 보기</summary>'
                    f'  <div class="body" style="margin-top:8px;color:#5C4A33;font-size:13px;">'
                    f'    <b>{T["original_excerpt"]}</b>: <em>{c.original_text}</em>'
                    f'  </div>'
                    f'  <div class="license-tag">📄 {c.license}</div>'
                    f'</details>'
                    f'<div style="margin-top:8px;font-size:12.5px;">'
                    f'<a href="{c.source_url}" target="_blank">{T["view_source"]}</a>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    if st.button(T["back_to_chat"], key="back_chat_bottom"):
        st.session_state.view = "quest"
        st.rerun()


# ─────────────────────────────────────────────────────────────
# 🎮 퀘스트 페이지 — AI가 4지선다 출제, 사용자가 풀고 사초 적립
# ─────────────────────────────────────────────────────────────
def _credit_bar() -> None:
    accuracy = (
        f"{st.session_state.total_correct}/{st.session_state.total_attempts}"
        if st.session_state.total_attempts else "0/0"
    )
    st.markdown(
        f'<div class="credit-bar">'
        f'  <span><b>📜 {T["credit_label"]}</b> '
        f'<span class="credit-num">{st.session_state.credits}</span></span>'
        f'  <span><b>🔥 {T["streak_label"]}</b> '
        f'<span class="credit-num">{st.session_state.streak}</span> '
        f'<span class="credit-best">(best {st.session_state.best_streak})</span></span>'
        f'  <span><b>🎯 {T["accuracy_label"]}</b> '
        f'<span class="credit-num">{accuracy}</span></span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _theme_options() -> dict[str, str]:
    """테마 키 -> 표시 라벨 매핑."""
    return {
        "all":          T["theme_all"],
        "palaces":      T["theme_palaces"],
        "gyeongju":     T["theme_gyeongju"],
        "danyang":      T["theme_danyang"],
        "andong":       T["theme_andong"],
        "imjin":        T["theme_imjin"],
        "joseon_kings": T["theme_joseon_kings"],
        "colonial":     T["theme_colonial"],
        "historians":   T["theme_historians"],
        "kculture":     T["theme_kculture"],
    }


def _course_options() -> dict[str, str]:
    """코스 키 -> 표시 라벨."""
    lang = st.session_state.language
    name_key = f"name_{lang}"
    return {cid: c.get(name_key, c["name_ko"]) for cid, c in COURSES.items()}


def _reset_question_state() -> None:
    st.session_state.current_q = None
    st.session_state.q_answered = False
    st.session_state.q_user_choice = None
    st.session_state.eliminated_options = []


def _generate_with_card(card: SourceCard) -> None:
    """주어진 카드로 문제를 생성해 세션에 저장 (스피너 포함).
    같은 카드라도 직전에 쓴 qtype을 피해서 매번 다른 각도로 출제.
    """
    # 이 카드에 대해 이번 세션에서 사용된 qtype 추적
    used_qtypes = st.session_state.setdefault("qtypes_per_card", {})
    avoid = used_qtypes.get(card.id, [])

    with st.spinner(T["quest_thinking"]):
        new_q = generate_question(
            card,
            language=st.session_state.language,
            mode=st.session_state.mode,
            avoid_qtypes=avoid[-3:],  # 최근 3개 유형 회피
        )
    # 이번 qtype 기록
    used_qtypes.setdefault(card.id, []).append(new_q.get("qtype", "?"))

    st.session_state.current_q = new_q
    st.session_state.q_answered = False
    st.session_state.q_user_choice = None
    st.session_state.eliminated_options = []
    st.session_state.q_seen_ids.append(card.id)
    # 문제 시작 시각 기록 — 시간 보너스/페널티 계산용
    st.session_state.q_start_time = time.time()


# ─── 캐릭터 모션 + 멘트 ───
# 정답 응원 (캐릭터 + 멘트)
CHEERS = [
    ("celebrate", "오오! 정답이외다! 사관도 놀랐소이다"),
    ("happy",     "참으로 박학다식하시오! 사관의 동무가 될 만하오"),
    ("proud",     "그렇소이다! 다음 단서로 가시지요"),
    ("start",     "정답이외다! 붓을 들고 적어 두겠소"),
    ("cheer",     "훌륭하외다! 연속 정답이라니, 사관도 부럽소이다"),
]
# 오답 조롱 (캐릭터 + 멘트)
TAUNTS = [
    ("facedown",      "허허… 그게 정답인 줄 아셨소이까? 졸자가 다 부끄럽소이다"),
    ("yawning",       "이런… 오늘은 두루마리를 좀 더 펼쳐 보시구려"),
    ("hmm",           "어이쿠, 옆 마을 무녀 할매도 이건 맞히실 텐데"),
    ("snack",         "사초가 슬슬 부족해 보이시는데, 한 문제만 더?"),
    ("confused",      "흠… 사관도 한참 생각해야 알 일이긴 하오만…"),
    ("facedown",      "어어… 졸자가 본 두루마리에는 분명 답이 있는데 말이외다"),
]

# 문제 유형 → 출제 시 캐릭터 포즈
QTYPE_POSES = {
    "source_inference":     "cheek",          # 사료 보며 생각
    "character_motivation": "hmm",            # 인물 생각 갸우뚱
    "place_significance":   "pointing",       # 장소 가리키기
    "wrong_compare":        "reading",        # 책 펴 비교
    "consequence":          "writing",        # 결과 기록
    "fallback":             "cheek",
}


def _result_character(is_correct: bool) -> tuple[str, str]:
    """결과에 맞는 캐릭터 포즈 + 멘트 (라운드마다 다르게)."""
    import random as _r
    pool = CHEERS if is_correct else TAUNTS
    # streak 또는 question count로 시드를 살짝 분산
    idx = (st.session_state.total_attempts +
           (1 if is_correct else 7)) % len(pool)
    return pool[idx]


def _time_bonus(elapsed: float) -> tuple[int, str]:
    """경과 시간 → 사초 보너스/페널티 + 안내 멘트."""
    if elapsed <= 15:
        return +5, f"⚡ {elapsed:.0f}초만에! +5 사초 시간 보너스"
    if elapsed <= 60:
        return 0, f"⏱ {elapsed:.0f}초 걸렸소이다"
    if elapsed <= 120:
        return -3, f"🐢 {elapsed:.0f}초… -3 사초 시간 페널티"
    return -5, f"💤 {elapsed:.0f}초… 사관이 잠들 뻔했소이다 (-5 사초)"


def render_quest_page() -> None:
    # ── 연승 milestone toast (직전 답변에서 set 된 메시지) ──
    _toast = st.session_state.pop("_pending_toast", None)
    if _toast:
        _msg, _icon = _toast
        try:
            st.toast(_msg, icon=_icon)
        except Exception:
            # 구버전 Streamlit fallback
            pass

    # ── 코스 종료 화면 ──
    if st.session_state.course_finished:
        cid = st.session_state.course_id
        total = course_card_count(cid)
        score = st.session_state.course_score
        tier = ending_tier(score, total)
        tier_msg = T.get(f"ending_{tier}", T["ending_apprentice"])
        # 칭호별 전용 일러스트 우선 — 파일 있으면 c_tier_<tier>.png 사용
        # 없으면 기존 포즈로 graceful fallback (asset 없어도 앱 작동)
        _tier_fallback = {
            "master":     "celebrate",
            "companion":  "happy",
            "apprentice": "careful_write",
            "novice":     "facedown",
        }
        from pathlib import Path as _PathTier
        _tier_png = (_PathTier(__file__).parent / "assets"
                     / f"c_tier_{tier}.png")
        if _tier_png.exists():
            char_pose = f"tier_{tier}"     # c_tier_master.png → char_img("tier_master")
            char_width = 150               # tier 일러스트는 살짝 크게
        else:
            char_pose = _tier_fallback.get(tier, "careful_write")
            char_width = 130

        course_name = _course_options().get(cid, cid)
        accuracy_pct = int(round(score / max(total, 1) * 100))
        # 상위 칭호일 때 컨페티 애니메이션 추가
        ending_cls = "quest-ending"
        if tier in ("master", "companion"):
            ending_cls += " celebration"
        st.markdown(
            f'<div class="{ending_cls}">'
            f'  <div class="ending-char">{char_img(char_pose, width=char_width)}</div>'
            f'  <div class="ending-text">'
            f'    <h3>{T["ending_title"]}</h3>'
            f'    <p class="ending-score">'
            f'{T["ending_score_line"].format(score=score, total=total)}</p>'
            f'    <p class="ending-tier">{tier_msg}</p>'
            f'    <div class="ending-meta">'
            f'      <span class="end-pill">🗺 {course_name}</span>'
            f'      <span class="end-pill">🎯 정답률 {accuracy_pct}%</span>'
            f'      <span class="end-pill">📜 모은 사초 {st.session_state.credits}</span>'
            f'      <span class="end-pill">🔥 최고 연승 {st.session_state.best_streak}</span>'
            f'    </div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # 공유 카드 — 텍스트 다운로드/복사용 (SNS 자랑·캡처 대용)
        tier_emoji = {
            "master": "🏆",
            "companion": "🌿",
            "apprentice": "📚",
            "novice": "🌱",
        }.get(tier, "📜")
        share_text = (
            f"{tier_emoji} 사초(史草) AI — {course_name}\n"
            f"{tier_msg}\n"
            f"🎯 {score}/{total} ({accuracy_pct}%) · "
            f"📜 사초 {st.session_state.credits} · "
            f"🔥 최고 연승 {st.session_state.best_streak}\n"
            f"https://sacho-ai.streamlit.app\n"
            f"#사초AI #한국사 #문체부AI공모전"
        )
        with st.expander("📤 결과 공유 / 캡처용 텍스트", expanded=False):
            st.code(share_text, language=None)
            st.download_button(
                "📄 결과 텍스트 저장 (.txt)",
                data=share_text,
                file_name=f"sacho_ai_result_{cid}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        # 3개 옵션 — 같은 코스 재도전 / 다른 코스 / 지도(랜딩)
        end_l, end_m, end_r = st.columns(3)
        with end_l:
            if st.button("🔁 " + T["ending_restart_btn"],
                         key="ending_restart",
                         use_container_width=True):
                st.session_state.course_finished = False
                st.session_state.course_idx = 0
                st.session_state.course_score = 0
                _reset_question_state()
                # 자동으로 첫 카드 생성 (사용자 한 번 더 클릭 안 해도 됨)
                if api_key_present:
                    first_card = pick_course_card(
                        st.session_state.course_id, 0
                    )
                    if first_card is not None:
                        _generate_with_card(first_card)
                st.rerun()
        with end_m:
            if st.button("🗺 다른 코스 고르기",
                         key="ending_pick_other",
                         use_container_width=True,
                         help="놀이 방식 선택 화면으로 — 코스/테마/근처 모두 가능"):
                st.session_state.course_finished = False
                st.session_state.course_idx = 0
                st.session_state.course_score = 0
                _reset_question_state()
                st.rerun()
        with end_r:
            if st.button("🏠 지도로 돌아가기",
                         key="ending_back_landing",
                         use_container_width=True,
                         help="랜딩 지도로 — 아무 모드나 다시 선택"):
                st.session_state.course_finished = False
                st.session_state.course_idx = 0
                st.session_state.course_score = 0
                _reset_question_state()
                # 랜딩 지도 강제 펼침 (사용자가 다음 액션 보기 쉽게)
                st.session_state.landing_map_collapsed = False
                st.rerun()
        return

    _credit_bar()

    q = st.session_state.current_q

    # ── 문제 없을 때 — 랜딩 지도 + 모드/주제 선택 + 시작 ──
    if q is None:
        # ── 퀘스트 랜딩 hero banner (이미지 있을 때만) ──
        # 문제 풀이 중에는 안 보임 (q is not None 일 때 자동 숨김)
        from pathlib import Path as _PathQH
        _qh_path = _PathQH(__file__).parent / "assets" / "hero_scene.png"
        if _qh_path.exists():
            import base64 as _b64qh
            _qh_b64 = _b64qh.b64encode(_qh_path.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="quest-hero-banner">'
                f'  <img src="data:image/png;base64,{_qh_b64}" alt="사관의 책상" />'
                f'</div>',
                unsafe_allow_html=True,
            )

        # API 키 누락 시 가장 위에 노출 — 클릭 후 알게 되는 일 방지
        if not api_key_present:
            st.markdown(
                '<div class="api-key-warn">'
                '  ⚠ <b>사관이 잠들어 있소이다.</b> '
                '관리자에게 API 키 설정을 요청해 주오. '
                '<small>(ANTHROPIC_API_KEY 환경변수)</small>'
                '</div>',
                unsafe_allow_html=True,
            )

        # 첫 화면: 지도 (사용자 위치 + 모든 게임 장소 카테고리 아이콘)
        render_landing_map()
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

        # ── 처음이라면 onboarding 카드 (사초·연승·정답률 의미 + 추천 시작) ──
        is_first_time = (
            st.session_state.total_attempts == 0
            and not st.session_state.q_seen_ids
        )
        if is_first_time:
            st.markdown(
                f'<div class="onboarding-card">'
                f'  <div class="onb-head">'
                f'    <span class="onb-badge">처음이오?</span>'
                f'    <h4>3가지만 알면 끝나오 ⤵</h4>'
                f'  </div>'
                f'  <div class="onb-grid">'
                f'    <div class="onb-cell">'
                f'      <div class="onb-icon">📜</div>'
                f'      <b>사초</b>'
                f'      <p>정답 <b>+10~15</b> (시간 보너스 ±5), 오답 <b>0</b>, 힌트 <b>-3</b>. '
                f'      모으면 칭호 획득.</p>'
                f'    </div>'
                f'    <div class="onb-cell">'
                f'      <div class="onb-icon">🔥</div>'
                f'      <b>연승</b>'
                f'      <p>연속 정답. 끊기면 0부터.</p>'
                f'    </div>'
                f'    <div class="onb-cell">'
                f'      <div class="onb-icon">🎯</div>'
                f'      <b>정답률</b>'
                f'      <p>맞춘 횟수 / 푼 횟수.</p>'
                f'    </div>'
                f'  </div>'
                f'  <div class="onb-rec">'
                f'    💡 <b>처음이라면 추천 →</b> "🗺 큐레이션 코스" → '
                f'    "정동·덕수궁 한 바퀴" (5문항, 10분).'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div class="quest-intro">'
            f'  <div class="quest-intro-char">{char_img("start", width=110)}</div>'
            f'  <div class="quest-intro-text">'
            f'    <h3>{T["quest_intro_title"]}</h3>'
            f'    <p>{T["quest_intro_desc"]}</p>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # 놀이 방식 선택 (라디오 — 코스 / 자유 테마 / 내 근처)
        play_modes = {
            T["play_mode_course"]: "course",
            T["play_mode_theme"]:  "theme",
            T["play_mode_nearby"]: "nearby",
        }
        cur_label = next((k for k, v in play_modes.items()
                          if v == st.session_state.play_mode), list(play_modes)[0])
        picked = st.radio(
            T["play_mode_label"],
            list(play_modes.keys()),
            index=list(play_modes.keys()).index(cur_label),
            horizontal=True,
            key="play_mode_radio",
        )
        st.session_state.play_mode = play_modes[picked]

        # 모드별 picker
        if st.session_state.play_mode == "nearby":
            st.markdown(
                f'<div class="nearby-hint">{T["nearby_hint"]}</div>',
                unsafe_allow_html=True,
            )
            # streamlit-geolocation 버튼 (사용자 권한 요청)
            loc = None
            try:
                from streamlit_geolocation import streamlit_geolocation
                loc = streamlit_geolocation()
            except Exception:
                st.error("위치 라이브러리 로드 실패. requirements 확인 필요.")
                return

            if loc and loc.get("latitude") is not None:
                lat = float(loc["latitude"])
                lon = float(loc["longitude"])
                st.session_state.user_geo = (lat, lon)

                # 3단계 트리거 — 현장(200m) / 도보권(2km) / 당일권(30km)
                on_site = pick_nearby_cards(lat, lon, max_km=0.2,
                                            exclude_ids=st.session_state.q_seen_ids[-5:])
                walk    = pick_nearby_cards(lat, lon, max_km=2.0,
                                            exclude_ids=st.session_state.q_seen_ids[-5:])
                day     = pick_nearby_cards(lat, lon, max_km=30.0,
                                            exclude_ids=st.session_state.q_seen_ids[-5:])

                if on_site:
                    tier_label = (f"🎯 <b>현장</b> (200m 안) 사적 {len(on_site)}곳 발견! "
                                  f"바로 그 자리에서 푸시오")
                    cards_to_show = on_site
                    radius_km = 0.2
                elif walk:
                    tier_label = (f"🚶 <b>도보권</b> (2km 안) {len(walk)}곳 사적이 있소이다")
                    cards_to_show = walk
                    radius_km = 2.0
                elif day:
                    tier_label = (f"🚆 <b>당일 이동권</b> (30km 안) {len(day)}곳 사적이 있소이다")
                    cards_to_show = day
                    radius_km = 30.0
                else:
                    st.warning(T["nearby_too_far"])
                    return

                st.markdown(
                    f'<div class="nearby-tier">{tier_label}</div>',
                    unsafe_allow_html=True,
                )

                # ── 큰 무작위 출제 버튼 (가까울수록 가중치 ↑) ──
                st.markdown('<div class="start-btn-wrap">', unsafe_allow_html=True)
                random_clicked = st.button(
                    "🎲 가까운 사적 중 무작위로 출제 받기",
                    key="quest_start_nearby_random",
                    use_container_width=True,
                )
                st.markdown('</div>', unsafe_allow_html=True)
                if random_clicked:
                    if not api_key_present:
                        st.error(T["api_key_missing_title"])
                        return
                    picked = pick_random_nearby(
                        lat, lon, max_km=radius_km,
                        exclude_ids=st.session_state.q_seen_ids[-5:],
                    )
                    if picked is None and cards_to_show:
                        picked = cards_to_show[0][0]
                    if picked is None:
                        st.error("근처 사료를 찾지 못했소이다.")
                        return
                    _generate_with_card(picked)
                    st.rerun()

                # ── 직접 골라서 출제 받기 (가까운 8곳) ──
                st.markdown(
                    '<div class="nearby-list-head">또는 직접 골라서 — '
                    '<small>(같은 자리도 다른 사료 + LLM이 매번 다른 문제 출제)</small>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                for i, (card, dist_km) in enumerate(cards_to_show[:8]):
                    dist_str = (
                        f"{dist_km*1000:.0f} m" if dist_km < 1
                        else f"{dist_km:.1f} km"
                    )
                    icon, color, cat_label = _site_category(card)
                    row_l, row_r = st.columns([5, 1])
                    with row_l:
                        st.markdown(
                            f'<div class="nearby-row">'
                            f'  <div class="nearby-row-title">'
                            f'    <span style="color:{color}">{icon}</span> '
                            f'    <b>{card.title}</b>'
                            f'  </div>'
                            f'  <div class="nearby-row-meta">'
                            f'    📍 {dist_str} · {card.place} · '
                            f'    <span class="cat-pill" style="background:{color}22;color:{color}">{cat_label}</span>'
                            f'  </div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with row_r:
                        if st.button("🎲", key=f"nearby_pick_{i}",
                                     help="이 사적에서 문제 받기 (매번 다른 문제)"):
                            if not api_key_present:
                                st.error(T["api_key_missing_title"])
                                return
                            _generate_with_card(card)
                            st.rerun()
            else:
                st.info(T["nearby_no_perm"])
            return

        # 코스 / 테마 셀렉트 — 풀-너비 단일 행 (위), 시작 버튼은 별도 행 (아래)
        # 이전 col_a/col_b 분할은 권역 태그가 추가되면 정렬이 어긋나 제거
        if st.session_state.play_mode == "course":
            courses = _course_options()
            course_keys = list(courses.keys())
            course_labels = [courses[k] for k in course_keys]
            cur_cid = st.session_state.course_id
            cur_idx = course_keys.index(cur_cid) if cur_cid in course_keys else 0
            picked_label = st.selectbox(
                T["course_label"],
                course_labels,
                index=cur_idx,
                key="course_select",
            )
            new_cid = course_keys[course_labels.index(picked_label)]
            if new_cid != st.session_state.course_id:
                st.session_state.course_id = new_cid
                st.session_state.course_idx = 0
                st.session_state.course_score = 0
            area = COURSES.get(new_cid, {}).get("area_ko", "")
            # ── 코스 preview 카드 (썸네일 있으면) ─ 없으면 area-tag 폴백 ──
            _course_thumb_html = course_thumb(new_cid, width=140)
            _total_cards = course_card_count(new_cid)
            if _course_thumb_html:
                st.markdown(
                    f'<div class="course-preview">'
                    f'  <div class="course-preview-thumb">{_course_thumb_html}</div>'
                    f'  <div class="course-preview-text">'
                    f'    <div class="course-preview-name">{picked_label}</div>'
                    f'    <div class="course-preview-meta">📍 {area or "—"}</div>'
                    f'    <div class="course-preview-cards">'
                    f'      🗺 단서 <b>{_total_cards}</b>개 · 예상 <b>{_total_cards * 2}분</b>'
                    f'    </div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            elif area:
                st.markdown(
                    f'<div class="area-tag">📍 권역 — {area}</div>',
                    unsafe_allow_html=True,
                )
        else:
            themes = _theme_options()
            theme_keys = list(themes.keys())
            theme_labels = [themes[k] for k in theme_keys]
            current_theme = st.session_state.quest_theme
            cur_t = theme_keys.index(current_theme) if current_theme in theme_keys else 0
            picked_label = st.selectbox(
                T["quest_theme_label"],
                theme_labels,
                index=cur_t,
                key="theme_select",
            )
            st.session_state.quest_theme = theme_keys[theme_labels.index(picked_label)]
            # K-콘텐츠 테마 선택 시 — "1905→2026 떨어진 사관" 페르소나 인트로
            # 전용 일러스트 (c_kculture_intro.png) 있으면 120px, 없으면 hmm 72px 폴백
            if st.session_state.quest_theme == "kculture":
                from pathlib import Path as _PathKC
                _kc_png = (_PathKC(__file__).parent / "assets"
                           / "c_kculture_intro.png")
                if _kc_png.exists():
                    _kc_char = char_img("kculture_intro", width=120)
                    _kc_char_cls = "kculture-intro-char kc-illust"
                else:
                    _kc_char = char_img("hmm", width=72)
                    _kc_char_cls = "kculture-intro-char"
                st.markdown(
                    f'<div class="kculture-intro">'
                    f'  <div class="{_kc_char_cls}">{_kc_char}</div>'
                    f'  <div class="kculture-intro-text">'
                    f'    <div class="kc-tag">🎬 K-콘텐츠 모드</div>'
                    f'    <b>1905년 정동에서 갑자기 2026년으로 떨어진 사관이외다.</b><br>'
                    f'    드라마·영화·예능 속 한국을 골라드리니, '
                    f'    <b>실제 사적</b>과 <b>가상 각색</b>을 가려내 보시구려. '
                    f'    <small>(케데헌·낭만닥터·정년이·도깨비·미스터션샤인 등 다수)</small>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # 시작 버튼 — 풀-너비, picker 바로 아래
        st.markdown('<div class="start-btn-wrap">', unsafe_allow_html=True)
        clicked = st.button(
            T["quest_start_btn"], key="quest_start", use_container_width=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
        if clicked:
            if not api_key_present:
                st.error(T["api_key_missing_title"])
                return
            if st.session_state.play_mode == "course":
                card = pick_course_card(
                    st.session_state.course_id,
                    st.session_state.course_idx,
                )
            else:
                card = pick_card(
                    st.session_state.quest_theme,
                    exclude_ids=st.session_state.q_seen_ids[-10:],
                )
            if card is None:
                st.error("코스 사료를 찾을 수 없소이다.")
                return
            _generate_with_card(card)
            st.rerun()
        return

    # ── 문제 표시 ──
    # 코스 진행 표시 + 전체 코스 지도
    if st.session_state.play_mode == "course":
        cid = st.session_state.course_id
        total = course_card_count(cid)
        idx_show = st.session_state.course_idx + 1
        course_name = _course_options()[cid]
        # 진행 dot 시리즈 — 지나온/현재/남은 단서 시각화
        dots_html = ''
        for _i in range(total):
            if _i < st.session_state.course_idx:
                _cls = 'done'
            elif _i == st.session_state.course_idx:
                _cls = 'current'
            else:
                _cls = ''
            dots_html += f'<div class="course-progress-step {_cls}"></div>'
        # 미니 코스 썸네일 (52px) — 진행 헤더 좌측 부착, 지속적 시각 정체성
        _mini_thumb = course_thumb(cid, width=52)
        _thumb_wrap = (
            f'<div class="course-progress-mini">{_mini_thumb}</div>'
            if _mini_thumb else ''
        )
        st.markdown(
            f'<div class="course-progress">'
            f'  {_thumb_wrap}'
            f'  <div class="course-progress-main">'
            f'    <div>'
            f'      <b>🗺 {course_name}</b>'
            f'      <span class="course-progress-meter">'
            f'        {idx_show}<small style="color:var(--ink-soft);font-size:13px;">/{total}</small>'
            f'      </span>'
            f'      · {T["course_score"]}: <b>'
            f'{st.session_state.course_score}/{idx_show - 1 if not st.session_state.q_answered else idx_show}'
            f'</b>'
            f'    </div>'
            f'    <div class="course-progress-bar">{dots_html}</div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # 코스 전체 지도 (모든 단서 위치 + 현재 강조 + 사용자 위치)
        render_course_map(
            cid, st.session_state.course_idx,
            user_loc=st.session_state.user_geo,
        )

    st.markdown(
        f'<div class="quest-q">'
        f'  <div class="quest-q-tag">Q.</div>'
        f'  <div class="quest-q-body">{q["question"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    answered = st.session_state.q_answered
    eliminated = set(st.session_state.eliminated_options)
    marks = ["①", "②", "③", "④"]

    # ── 키보드 단축키 (1·2·3·4 답안, H 힌트, N 다음/Enter)
    # 한 페이지당 단 한 번만 listener 등록 (window flag)
    st.markdown(
        """
        <script>
        (function() {
            if (window._sacho_kbd_installed) return;
            window._sacho_kbd_installed = true;
            const marks = ['①', '②', '③', '④'];
            const hintRegex = /힌트|hint|ヒント|提示/i;
            const nextRegex = /다음|next|次の|下一|마무리/i;
            function clickByText(matcher) {
                const candidates = document.querySelectorAll(
                    'button[data-testid="baseButton-secondary"], '
                    + '[data-testid="stButton"] button'
                );
                for (const btn of candidates) {
                    const txt = (btn.innerText || '').trim();
                    if (matcher(txt)) { btn.click(); return true; }
                }
                return false;
            }
            document.addEventListener('keydown', function(e) {
                // 입력 필드에서는 비활성
                const tag = (e.target && e.target.tagName) || '';
                if (tag === 'INPUT' || tag === 'TEXTAREA') return;
                if (e.ctrlKey || e.metaKey || e.altKey) return;
                if (e.key >= '1' && e.key <= '4') {
                    const idx = parseInt(e.key, 10) - 1;
                    clickByText(t => t.startsWith(marks[idx]));
                } else if (e.key.toLowerCase() === 'h') {
                    clickByText(t => hintRegex.test(t));
                } else if (e.key.toLowerCase() === 'n' || e.key === 'Enter') {
                    clickByText(t => nextRegex.test(t));
                }
            });
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    # ── 답변 전 — 힌트 + 4지선다 ──
    if not answered:
        # ── 시간 보너스 인라인 힌트 (시간 압박감) ──
        # 단순한 가이드 라인 — JS-기반 live 타이머는 Streamlit rerun과 충돌
        st.markdown(
            '<div class="time-hint-row">'
            '  <span class="time-hint-pill bonus">⚡ ~15초 <b>+5 사초</b></span>'
            '  <span class="time-hint-pill neutral">⏱ ~1분 <b>0</b></span>'
            '  <span class="time-hint-pill penalty">🐢 ~2분 <b>-3 사초</b></span>'
            '  <span class="time-hint-pill bad">💤 그 이상 <b>-5 사초</b></span>'
            '</div>'
            '<div class="kbd-hint-row">'
            '  ⌨ <span class="kbd-key">1</span><span class="kbd-key">2</span>'
            '  <span class="kbd-key">3</span><span class="kbd-key">4</span> 답안 · '
            '  <span class="kbd-key">H</span> 힌트 · '
            '  <span class="kbd-key">N</span> 다음'
            '</div>',
            unsafe_allow_html=True,
        )
        # ── 힌트 행 (이전 col 분할은 우측이 비어 어색했음 — 단일 행으로) ──
        # quest-hint-zone 마커 → :has() 로 hint 버튼 전용 스타일 매칭
        st.markdown(
            '<div class="quest-hint-zone"></div>', unsafe_allow_html=True,
        )
        if eliminated:
            st.markdown(
                f'<div class="hint-tag hint-used-tag">{T["hint_used"]}</div>',
                unsafe_allow_html=True,
            )
        elif st.session_state.credits >= 3:
            if st.button(T["hint_btn"], key="quest_hint",
                         use_container_width=True):
                wrong = [i for i in range(4) if i != q["correct_idx"]]
                _random.shuffle(wrong)
                st.session_state.eliminated_options = wrong[:2]
                st.session_state.credits -= 3
                st.rerun()
        else:
            st.markdown(
                f'<div class="hint-tag hint-locked-tag">{T["hint_locked"]}</div>',
                unsafe_allow_html=True,
            )
        # zone-end 마커 — :has() reset 으로 hint 스타일 영향 종료
        st.markdown(
            '<div class="quest-hint-end"></div>', unsafe_allow_html=True,
        )

        # 4지선다 버튼 — 마커 div 로 zone 정의 (CSS ~ 형제 선택자가 stamp 스타일 적용)
        st.markdown('<div class="quest-opts-zone"></div>', unsafe_allow_html=True)
        for i, opt in enumerate(q["options"]):
            if i in eliminated:
                st.markdown(
                    f'<div class="opt-eliminated">{marks[i]}  {opt} '
                    f'<small>{T["option_eliminated"]}</small></div>',
                    unsafe_allow_html=True,
                )
                continue
            if st.button(
                f"{marks[i]}  {opt}",
                key=f"quest_opt_{i}",
                use_container_width=True,
            ):
                st.session_state.q_user_choice = i
                st.session_state.q_answered = True
                st.session_state.total_attempts += 1
                # 경과 시간 계산 + 보너스
                elapsed = (
                    time.time() - st.session_state.q_start_time
                    if st.session_state.q_start_time else 30.0
                )
                st.session_state.last_elapsed = elapsed
                bonus, _ = _time_bonus(elapsed)
                st.session_state.last_bonus = bonus
                is_correct = (i == q["correct_idx"])
                if is_correct:
                    st.session_state.credits += 10 + bonus
                    st.session_state.streak += 1
                    st.session_state.total_correct += 1
                    if st.session_state.streak > st.session_state.best_streak:
                        st.session_state.best_streak = st.session_state.streak
                    # 연승 milestone — 다음 render 시 toast 표시 (장난스러움)
                    _s = st.session_state.streak
                    _milestone_msgs = {
                        3:  ("🔥 3연승! 사관이 놀라기 시작했소이다", "🔥"),
                        5:  ("🔥🔥 5연승! 두루마리에 이름 적히는 중", "✨"),
                        10: ("🏆 10연승! 사관의 으뜸 후보이시오", "🏆"),
                        15: ("👑 15연승! 사초의 전설로 기록 중", "👑"),
                        20: ("🎊 20연승! 사관이 절을 올리오", "🎊"),
                    }
                    if _s in _milestone_msgs:
                        msg, icon = _milestone_msgs[_s]
                        st.session_state._pending_toast = (msg, icon)
                else:
                    # 오답이면 시간 페널티만 적용 (보너스 없음)
                    if bonus < 0:
                        st.session_state.credits = max(0, st.session_state.credits + bonus)
                    # 연승이 끊긴 순간이라면 그 사실도 토스트 (3 이상에서만)
                    if st.session_state.streak >= 3:
                        st.session_state._pending_toast = (
                            f"💔 {st.session_state.streak}연승이 끊겼소이다… 다시 한 번",
                            "💔",
                        )
                    st.session_state.streak = 0
                # 코스 점수
                if st.session_state.play_mode == "course" and is_correct:
                    st.session_state.course_score += 1
                st.rerun()
        # zone-end 마커: 이후 stButton 은 stamp 스타일 reset (이 함수는 곧 return 하지만
        # 안전을 위해 명시)
        st.markdown('<div class="quest-opts-end"></div>', unsafe_allow_html=True)
        return

    # ── 답변 후 — 결과 + 캐릭터 멘트 + 시간 + 선지 회고 ──
    user = st.session_state.q_user_choice
    correct = q["correct_idx"]
    is_correct = (user == correct)
    char_pose, taunt_text = _result_character(is_correct)
    _, time_msg = _time_bonus(st.session_state.last_elapsed)

    result_cls = "correct" if is_correct else "wrong"
    result_label = T["quest_correct"] if is_correct else (
        f"{T['quest_wrong']} <b>{marks[correct]} {q['options'][correct]}</b>"
    )

    # 동적 다음 버튼 라벨 — 결과 패널 상·하 공용으로 미리 계산
    if st.session_state.play_mode == "course":
        _total = course_card_count(st.session_state.course_id)
        _next_idx = st.session_state.course_idx + 1
        if _next_idx > _total:
            _btn_label = f"🏁 코스 마무리 — 칭호 확인 ({_total}/{_total})"
            _btn_quick = "🏁 코스 마무리"
        else:
            _btn_label = f"📜 다음 단서로 ({_next_idx}/{_total})"
            _btn_quick = f"⏭ 다음 단서 ({_next_idx}/{_total})"
    else:
        _btn_label = T["quest_next_btn"]
        _btn_quick = "⏭ 다음 문제"

    st.markdown(
        f'<div class="quest-result-panel {result_cls}">'
        f'  <div class="qr-char">{char_img(char_pose, width=100)}</div>'
        f'  <div class="qr-body">'
        f'    <div class="qr-label">{result_label}</div>'
        f'    <div class="qr-taunt">"{taunt_text}"</div>'
        f'    <div class="qr-time">{time_msg}</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── 결과 패널 바로 아래: "빠른 다음" 작은 버튼 (해설/카드 건너뛰기) ──
    quick_l, quick_r = st.columns([3, 2])
    with quick_r:
        if st.button(_btn_quick, key="quest_next_quick",
                     use_container_width=True,
                     help="해설·사료 카드를 건너뛰고 다음 문제로 바로 이동"):
            st.session_state._advance_next = True
            st.rerun()

    # 회고 (정답=녹색, 오답=취소선)
    rows = []
    for i, opt in enumerate(q["options"]):
        cls = ""
        if i == correct:
            cls = "opt-correct"
        elif i == user:
            cls = "opt-wrong"
        rows.append(f'<div class="opt-row {cls}">{marks[i]} {opt}</div>')
    st.markdown('<div class="opt-recap">' + "".join(rows) + '</div>',
                unsafe_allow_html=True)

    # 선지별 코멘트 (option_notes)
    notes = q.get("option_notes") or []
    if any(notes):
        st.markdown(f"##### {T['option_notes_title']}")
        note_html = '<div class="opt-notes-block">'
        for i, opt in enumerate(q["options"]):
            note = notes[i] if i < len(notes) else ""
            row_cls = "note-correct" if i == correct else "note-wrong"
            note_html += (
                f'<div class="opt-note-row {row_cls}">'
                f'<span class="opt-note-mark">{marks[i]}</span>'
                f'<div><b>{opt}</b><br><small>{note}</small></div>'
                f'</div>'
            )
        note_html += '</div>'
        st.markdown(note_html, unsafe_allow_html=True)

    # 본 해설
    st.markdown(f"##### {T['quest_explanation']}")
    st.markdown(q["explanation"])

    # 사료 카드 + 지도
    card_id = q["card_id"]
    cards = [c for c in load_corpus() if c.id == card_id]
    if cards:
        render_evidence_cards(cards)
        render_evidence_map(cards)
        for cc in cards:
            st.session_state.collection[cc.id] = cc

    # 다음 문제 / 코스 다음 단서 / 코스 종료
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    next_clicked = st.button(
        _btn_label, key="quest_next", use_container_width=True
    )
    # 두 위치(상단 빠른 버튼 + 하단 버튼)에서 동일 advance 트리거 처리
    if next_clicked or st.session_state.pop("_advance_next", False):
        if st.session_state.play_mode == "course":
            st.session_state.course_idx += 1
            if st.session_state.course_idx >= course_card_count(st.session_state.course_id):
                st.session_state.course_finished = True
                _reset_question_state()
                st.rerun()
                return
            # 다음 코스 사료
            next_card = pick_course_card(
                st.session_state.course_id, st.session_state.course_idx
            )
            if next_card is None:
                st.session_state.course_finished = True
                _reset_question_state()
            else:
                _generate_with_card(next_card)
        else:
            _reset_question_state()
        st.rerun()


def render_meta(usage: dict | None, rag_cards: list[SourceCard]) -> None:
    if usage:
        st.markdown(
            f"<div class='meta-row'>"
            f"<span><b>{T['tokens_in']}</b> {usage.get('input_tokens', 0):,}</span>"
            f"<span><b>{T['tokens_out']}</b> {usage.get('output_tokens', 0):,}</span>"
            f"<span><b>{T['est_cost_krw']}</b> ₩{usage.get('est_cost_krw', 0):.2f}</span>"
            f"<span style='opacity:0.55;'>· {usage.get('model', '-')}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    if st.session_state.show_rag_debug and rag_cards:
        with st.expander(T["rag_debug_title"], expanded=False):
            df = pd.DataFrame(
                [
                    {"id": c.id, "title": c.title, "score": c.score,
                     "matched": ", ".join(c.matched_tokens)}
                    for c in rag_cards
                ]
            )
            st.dataframe(df, hide_index=True, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# 뷰 라우팅
# ─────────────────────────────────────────────────────────────
if st.session_state.view == "collection":
    render_collection_page()
    st.stop()

if st.session_state.view == "quest":
    render_quest_page()
    st.stop()


# ─────────────────────────────────────────────────────────────
# 빈 화면: 인사 + 추천 카드
# ─────────────────────────────────────────────────────────────
if not st.session_state.messages:
    # API 키 누락 시 빈 인사 위에 미리 경고 (입력 후에야 에러 받는 일 방지)
    if not api_key_present:
        st.markdown(
            '<div class="api-key-warn">'
            '  ⚠ <b>사관이 잠들어 있소이다.</b> '
            '관리자에게 API 키 설정을 요청해 주오. '
            '<small>(ANTHROPIC_API_KEY 환경변수)</small>'
            '</div>',
            unsafe_allow_html=True,
        )

    greeting = GREETING_BY_LANG[st.session_state.language]
    st.markdown(
        f'<div class="greeting-card">'
        f'  <div class="greeting-char">{char_img("umbrella", width=130)}</div>'
        f'  <div class="greeting-bubble">{greeting}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Why 카드는 게이트(로그인) 화면으로 이동 — 메인에서는 노출하지 않음

    st.markdown(
        f'<div class="suggest-section"><h5>{T["suggested_header"]}</h5></div>',
        unsafe_allow_html=True,
    )
    questions = SUGGESTED_QUESTIONS_BY_LANG[st.session_state.language]
    SUGGEST_POSES = ["start", "celebrate", "careful_write", "books"]
    qcols = st.columns(len(questions))
    for i, q in enumerate(questions):
        with qcols[i]:
            pose = SUGGEST_POSES[i % len(SUGGEST_POSES)]
            st.markdown(
                f'<div class="suggest-char">{char_img(pose, width=90)}</div>',
                unsafe_allow_html=True,
            )
            if st.button(q, key=f"suggest_{i}", use_container_width=True):
                st.session_state._pending_query = q
                st.rerun()


# ─────────────────────────────────────────────────────────────
# 이전 메시지 렌더링
# ─────────────────────────────────────────────────────────────
MOOD_EMOJI = {"사료 확인됨": "✨", "AI 각색": "🖌", "추정": "🌫"}

for msg in st.session_state.messages:
    if msg["role"] == "assistant":
        avatar = MOOD_EMOJI.get(msg.get("badge", ""), "📜")
    else:
        avatar = "🙋"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg["role"] == "assistant":
            if msg.get("badge"):
                st.markdown(
                    render_badge_html(msg["badge"], st.session_state.language),
                    unsafe_allow_html=True,
                )
            st.markdown(msg["content"])
            if msg.get("cards"):
                render_evidence_cards(msg["cards"])
                render_evidence_map(msg["cards"])
            render_meta(msg.get("usage"), msg.get("cards", []))
        else:
            st.markdown(msg["content"])


# ─────────────────────────────────────────────────────────────
# 사용자 입력
# ─────────────────────────────────────────────────────────────
pending = st.session_state.pop("_pending_query", None)
user_query = pending or st.chat_input(T["placeholder"])

if user_query:
    if not api_key_present:
        with st.chat_message("user", avatar="🙋"):
            st.markdown(user_query)
        with st.chat_message("assistant", avatar="💤"):
            st.error(
                f"{T['api_key_missing_title']}\n\n"
                f"{T['api_key_missing_body']}\n\n"
                "```\nANTHROPIC_API_KEY=sk-ant-...\n```"
            )
        st.stop()

    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user", avatar="🙋"):
        st.markdown(user_query)

    cards = search_corpus(user_query, top_k=3, min_score=0.6)

    history_msgs: list[dict] = []
    for m in st.session_state.messages[-9:-1]:
        if m["role"] in ("user", "assistant"):
            history_msgs.append({"role": m["role"], "content": m["content"]})

    with st.chat_message("assistant", avatar="📜"):
        placeholder = st.empty()
        placeholder.markdown(
            f'<div class="thinking">'
            f'<span class="thinking-char">{char_img("writing", width=60)}</span>'
            f'<span>{T["thinking"]}<span class="thinking-dots"></span></span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        full = ""
        usage_box: dict = {}

        def _capture_usage(u: dict) -> None:
            usage_box.update(u)

        try:
            for chunk in stream_sagwan_response(
                query=user_query,
                cards=cards,
                history=history_msgs,
                language=st.session_state.language,
                mode=st.session_state.mode,
                on_complete=_capture_usage,
            ):
                full += chunk
                visible = sanitize_streaming_text(full)
                if visible:
                    placeholder.markdown(visible + " ▌")
        except Exception as e:
            placeholder.empty()
            st.error(f"{T['api_error']}: {e}")
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                st.session_state.messages.pop()
            st.stop()

        badge, source_ids, body = parse_response(full)
        placeholder.empty()
        st.markdown(
            render_badge_html(badge, st.session_state.language),
            unsafe_allow_html=True,
        )
        st.markdown(body)

        if source_ids:
            cited_cards = [c for c in cards if c.id in source_ids]
            if not cited_cards:
                cited_cards = cards
        else:
            cited_cards = cards

        render_evidence_cards(cited_cards)
        render_evidence_map(cited_cards)
        render_meta(usage_box or None, cards)

    st.session_state.messages.append({
        "role": "assistant",
        "content": body,
        "badge": badge,
        "source_ids": source_ids,
        "cards": cited_cards,
        "usage": usage_box or None,
    })

    # 보관함에 새로 마주한 사료 누적 (id 기준 dedupe)
    for _c in cited_cards or []:
        st.session_state.collection[_c.id] = _c


# ─────────────────────────────────────────────────────────────
# 푸터 — 걸어가는 사관 + 부드러운 한 줄 (개발 메타 노출 X)
# ─────────────────────────────────────────────────────────────
FOOTER_TAGLINE = {
    "ko": "당신이 쓰는, 살아 있는 실록.",
    "en": "A living chronicle, written with you.",
    "ja": "あなたと書く、生きた実録。",
    "zh": "与你共同写就的、活着的実録。",
}
FOOTER_ATTRIB = {
    "ko": (
        "데이터: 국사편찬위원회 「조선왕조실록·승정원일기·한국사DB」 · "
        "한국고전번역원 「한국고전종합DB」 · 문화재청 「문화재 공간정보」 · "
        "한국관광공사 「TourAPI 4.0·Visit Korea」 · "
        "국립국악원·한국공예디자인문화진흥원 「한복·전통문양·국악」 (공모전 특별제공) · "
        "지자체 향토 사료 — 공공누리/공공데이터포털 라이선스 준수."
    ),
    "en": (
        "Data: National Institute of Korean History (Annals of Joseon, Seungjeongwon Ilgi, Korean History DB) · "
        "ITKC Korean Classics DB · Cultural Heritage Administration (heritage geo-data) · "
        "Korea Tourism Organization (TourAPI 4.0, Visit Korea) · "
        "National Gugak Center & KCDF (hanbok, traditional patterns, Korean music — competition-provided) · "
        "local government archives — used under KOGL / public-data licenses."
    ),
    "ja": (
        "データ: 国史編纂委員会(朝鮮王朝実録・承政院日記・韓国史DB)・"
        "韓国古典翻訳院(韓国古典総合DB)・文化財庁(文化財空間情報)・"
        "韓国観光公社(TourAPI 4.0・Visit Korea)・"
        "国立国楽院・韓国工芸デザイン文化振興院(韓服・伝統文様・国楽 — コンテスト特別提供)・"
        "自治体郷土資料 — 公共ヌリ/公共データポータルに準拠。"
    ),
    "zh": (
        "数据:国史编纂委员会(朝鲜王朝实录·承政院日记·韩国史DB)·"
        "韩国古典翻译院(韩国古典综合DB)·文化财厅(文化遗产空间信息)·"
        "韩国观光公社(TourAPI 4.0·Visit Korea)·"
        "国立国乐院·韩国工艺设计文化振兴院(韩服·传统纹样·国乐 — 大赛特别提供数据)·"
        "地方政府乡土资料 — 遵守公共Nuri/公共数据门户许可。"
    ),
}
st.markdown(
    f'<div style="text-align:center;">'
    f'<div class="footer-strip">'
    f'  <div class="footer-char">{char_img("cheer", width=58)}</div>'
    f'  <div class="footer-text">{FOOTER_TAGLINE[st.session_state.language]}</div>'
    f'</div>'
    f'<div class="footer-attrib">'
    f'  📜 {FOOTER_ATTRIB[st.session_state.language]}'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)
