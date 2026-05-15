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
from core.rag import search_corpus, SourceCard
from core.badge import parse_response, render_badge_html, sanitize_streaming_text
from core.prompts import GREETING_BY_LANG, SUGGESTED_QUESTIONS_BY_LANG, UI_TEXT
from core.character import (
    LOGO_SVG, MAIN_SVG, SLEEPING_SVG, WALKING_SVG, POINTING_SVG,
    CONFUSED_SVG, PEEKING_SVG, SUGGEST_CHARS, SHUSH_SVG, LOCK_SVG,
)


st.set_page_config(
    page_title="사초 AI — 졸린 사관과 함께",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─────────────────────────────────────────────────────────────
# 스타일 — 모던 큐트 / 요시타케 풍
# ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Gowun+Batang:wght@400;700&family=Nanum+Pen+Script&family=Noto+Sans+KR:wght@400;500;700&display=swap');

    :root {
        --cream: #FDF8EE;
        --oat: #F4ECD9;
        --paper: #FBF3E0;
        --ink: #3A2A1F;             /* 따뜻한 다크 브라운 (캐릭터 외곽선과 통일) */
        --ink-soft: #6B5440;
        --red: #C97064;
        --red-deep: #A8554A;
        --navy: #4A5B73;
        --mustard: #DBB871;
        --pink: #F2B5B5;
        --sage: #B5C5A8;
        --sky: #B8D4DE;
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

    /* ── 전체 배경 (한지 + 따뜻한 워시) ─────────────────────── */
    .stApp {
        background:
            radial-gradient(circle at 18% 8%, rgba(219,184,113,0.14) 0, transparent 38%),
            radial-gradient(circle at 88% 92%, rgba(201,112,100,0.10) 0, transparent 45%),
            radial-gradient(circle at 92% 12%, rgba(181,197,168,0.10) 0, transparent 35%),
            linear-gradient(180deg, #FFFBF1 0%, #F7EDD9 100%);
    }

    .main .block-container {
        max-width: 1180px;
        padding: 1rem 2rem 4rem 2rem;
        font-family: 'Noto Sans KR', sans-serif;
        color: var(--ink);
    }
    h1, h2, h3, h4 {
        font-family: 'Gowun Batang', 'Gowun Dodum', serif;
        color: var(--ink);
        letter-spacing: -0.3px;
    }

    /* ── 가로형 톱바 ─────────────────────────────────────── */
    .topbar {
        display: flex; align-items: center; gap: 14px;
        padding: 12px 18px;
        background: rgba(255, 251, 241, 0.85);
        border: 2.5px solid var(--ink);
        border-radius: 22px;
        box-shadow: 4px 4px 0 var(--ink);
        margin: 4px 0 22px 0;
        position: relative;
        backdrop-filter: blur(6px);
    }
    .topbar-logo-link {
        display: inline-block;
        text-decoration: none;
        color: inherit;
        border-radius: 14px;
        padding: 4px 8px;
        transition: transform 0.12s, background 0.15s;
        cursor: pointer;
    }
    .topbar-logo-link:hover {
        background: rgba(255, 231, 160, 0.55);
        transform: translateY(-1px);
    }
    .topbar-logo-link:active { transform: translateY(1px); }
    .topbar-logo {
        display: flex; align-items: center; gap: 10px;
        flex: 1; min-width: 0;
    }
    .topbar-logo .logo-svg { animation: bob 4s ease-in-out infinite; }
    @keyframes bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
    .topbar-logo .brand {
        font-family: 'Gowun Batang', serif;
        font-weight: 700;
        font-size: 22px;
        line-height: 1.1;
        color: var(--ink);
    }
    .topbar-logo .brand-sub {
        font-family: 'Nanum Pen Script', cursive;
        font-size: 15px; color: var(--ink-soft); opacity: 0.8;
        margin-left: 4px;
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
        background:
            radial-gradient(circle at 25% 25%, #FFF6DC 0, transparent 60%),
            linear-gradient(135deg, var(--paper) 0%, var(--oat) 100%);
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

    /* ── 추천 질문 카드 그리드 (캐릭터 + 버튼 묶음) ────────── */
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

    /* 채팅 input 영역 — 부드럽게 */
    [data-testid="stChatInput"] textarea {
        border-radius: 18px !important;
        border: 2.5px solid var(--ink) !important;
        background: var(--cream) !important;
        font-family: 'Gowun Batang', serif !important;
        box-shadow: 2px 2px 0 var(--ink) !important;
    }

    /* ─── 📜 사료 보관함 페이지 ─── */
    .collection-header {
        display: flex; align-items: center; gap: 16px;
        background:
            radial-gradient(circle at 20% 20%, #FFF6DC 0, transparent 55%),
            linear-gradient(135deg, var(--paper) 0%, var(--oat) 100%);
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

    /* ─── 🔐 비밀번호 게이트 (초 귀엽게) ─── */
    .gate-wrap {
        display: flex; justify-content: center;
        padding: 36px 12px 60px 12px;
    }
    .gate-card {
        width: 100%; max-width: 520px;
        background:
            radial-gradient(circle at 25% 20%, #FFF6DC 0, transparent 55%),
            linear-gradient(135deg, var(--paper) 0%, var(--oat) 100%);
        border: 3px solid var(--ink);
        border-radius: 28px;
        padding: 28px 28px 22px 28px;
        box-shadow: 6px 6px 0 var(--ink);
        position: relative;
        overflow: visible;
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

    /* 모바일 폴백 */
    @media (max-width: 720px) {
        .hero { flex-direction: column; align-items: flex-start; }
        .hero-char { align-self: center; flex: 0 0 110px; }
        .hero-peek { display: none; }
        .greeting-card { flex-direction: column; align-items: stretch; }
        .greeting-bubble::before, .greeting-bubble::after { display: none; }
        .topbar { flex-wrap: wrap; gap: 8px; }
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
        st.session_state.view = "chat"          # "chat" | "collection"
    if "collection" not in st.session_state:
        st.session_state.collection = {}        # id -> SourceCard


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


def render_password_gate(expected: str) -> None:
    """초 귀여운 비밀번호 게이트. 통과 시 st.session_state.auth_ok = True."""
    attempts = st.session_state.get("auth_attempts", 0)
    shake_class = " gate-shake" if st.session_state.pop("_just_failed", False) else ""

    st.markdown(
        f'<div class="gate-wrap">'
        f'<div class="gate-card{shake_class}">'
        f'  <div class="gate-chars">'
        f'    <div class="char-main">{MAIN_SVG}</div>'
        f'    <div class="char-lock">{LOCK_SVG}</div>'
        f'  </div>'
        f'  <div class="gate-bubble">'
        f'    어어… 이 두루마리는 <b>잠금</b>이 걸려 있소이다.<br>'
        f'    암호를 살짝 속삭여 주시구려…'
        f'    <small>(Hmm… this scroll is locked. Whisper the password.)</small>'
        f'  </div>',
        unsafe_allow_html=True,
    )

    with st.form("pw_form", clear_on_submit=True):
        pw = st.text_input(
            "암호",
            type="password",
            label_visibility="collapsed",
            placeholder="• • • • • •",
            key="pw_input",
        )
        submitted = st.form_submit_button("들여 보내 주시오")

    if attempts > 0:
        st.markdown(
            '<div class="gate-err">'
            '어어… 그 암호가 아닌 것 같소이다… 다시 한 번?'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="gate-foot">— 졸린 사관이 지키는 두루마리 —</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if submitted:
        if pw == expected:
            st.session_state.auth_ok = True
            st.session_state.auth_attempts = 0
            st.rerun()
        else:
            st.session_state.auth_attempts = attempts + 1
            st.session_state._just_failed = True
            st.rerun()


_pw = _expected_password()
if _pw and not st.session_state.get("auth_ok"):
    render_password_gate(_pw)
    st.stop()


# ─────────────────────────────────────────────────────────────
# 여백 데코 캐릭터 (좌하·우하, 큰 화면에서만 보임)
# ─────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="deco-left">{SLEEPING_SVG}</div>'
    f'<div class="deco-right">{PEEKING_SVG}</div>',
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────
# 가로형 톱바
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="topbar-tools">', unsafe_allow_html=True)

bar_cols = st.columns([2.3, 1.0, 1.0, 1.1, 0.7, 0.7])

with bar_cols[0]:
    st.markdown(
        f'<a href="?home=1" target="_self" class="topbar-logo-link" '
        f'title="첫 화면으로 돌아가기">'
        f'<div class="topbar-logo">'
        f'<div class="logo-svg">{LOGO_SVG}</div>'
        f'<div><div class="brand">사초(史草) AI</div>'
        f'<div class="brand-sub">— 졸린 사관과 함께 —</div></div>'
        f'</div>'
        f'</a>',
        unsafe_allow_html=True,
    )

with bar_cols[1]:
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
        st.session_state.language = lang_options[lang_label]
        st.session_state.messages = []
        st.rerun()

with bar_cols[2]:
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

with bar_cols[3]:
    n_seen = len(st.session_state.collection)
    label = f"{T['collection_btn']} ({n_seen})" if n_seen else T["collection_btn"]
    is_in_collection = st.session_state.view == "collection"
    if st.button(label, key="btn_collection", use_container_width=True,
                 help="내가 마주한 사료 모음"):
        st.session_state.view = "chat" if is_in_collection else "collection"
        st.rerun()

with bar_cols[4]:
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

with bar_cols[5]:
    if st.button("🔄", help=T["reset_label"], use_container_width=True):
        st.session_state.messages = []
        st.session_state.collection = {}
        st.session_state.view = "chat"
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 헤더 (큰 사관 + 말풍선 타이틀 + 빼꼼 캐릭터)
# ─────────────────────────────────────────────────────────────
HEADER_TEXT = {
    "ko": ("사관(史官)과 두런두런",
           "1896년 정동에서 일어난 어떤 일을, 졸린 사관과 함께 살살 풀어 보시구려."),
    "en": ("Chatting with the Sleepy Sagwan",
           "Let's gently unravel what happened in Jeongdong, 1896, together with this drowsy historian."),
    "ja": ("ねむたい史官とぽつぽつ",
           "1896年、貞洞で起きたあの一件を、眠そうな史官と一緒にゆるゆると解いてみましょう。"),
    "zh": ("和犯困的史官闲谈",
           "1896年贞洞那桩事,我们和这位犯困的小史官慢慢理一理吧。"),
}
title, subtitle = HEADER_TEXT[st.session_state.language]
st.markdown(
    f'<div class="hero">'
    f'  <div class="hero-char">{MAIN_SVG}</div>'
    f'  <div class="hero-text">'
    f'    <h1>📜 {title}</h1>'
    f'    <p>{subtitle}</p>'
    f'  </div>'
    f'  <div class="hero-peek">{CONFUSED_SVG}</div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────
# 뷰 분기 — 사료 보관함이면 본 페이지에서 종료 (헤더는 위에서 이미 그려졌음)
# ─────────────────────────────────────────────────────────────
def render_evidence_cards(cards: list[SourceCard]) -> None:
    if not cards:
        return
    st.markdown(f"##### {T['evidence_header']}")
    for c in cards:
        st.markdown(
            f'<div class="evidence-card">'
            f'<h4>📜 {T["evidence_id"]} {c.id} · {c.title}</h4>'
            f'<div class="meta">📅 {c.date} &nbsp;|&nbsp; 📍 {c.place} '
            f'&nbsp;|&nbsp; 📖 {c.source}</div>'
            f'<div class="body">{c.summary}</div>'
            f'<div class="body" style="margin-top:8px;color:#5C4A33;font-size:13.5px;">'
            f'<b>{T["original_excerpt"]}</b>: <em>{c.original_text}</em></div>'
            f'<div style="margin-top:10px;font-size:12.5px;">'
            f'<a href="{c.source_url}" target="_blank">{T["view_source"]}</a>'
            f'&nbsp;&nbsp;<span style="color:#8a7560;">📄 {c.license}</span>'
            f'</div></div>',
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


def render_collection_page() -> None:
    """사관과 함께 본 사료 보관함."""
    cards = list(st.session_state.collection.values())
    n = len(cards)

    if n == 0:
        st.markdown(
            f'<div class="collection-empty">'
            f'  <div class="collection-empty-char">{SLEEPING_SVG}</div>'
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
        f'  <div class="collection-char">{POINTING_SVG}</div>'
        f'  <div class="collection-head-text">'
        f'    <h3>📜 {T["collection_title"]}</h3>'
        f'    <p>{T["collection_sub"]} <b>{n}</b>{T["collection_count"]}.</p>'
        f'  </div>'
        f'  <div class="collection-char-side">{CONFUSED_SVG}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # 2-column 그리드 (좁은 화면에서는 자동 1단)
    cols = st.columns(2)
    for i, c in enumerate(sorted(cards, key=lambda x: x.date)):
        with cols[i % 2]:
            st.markdown(
                f'<div class="evidence-card">'
                f'<h4>📜 {T["evidence_id"]} {c.id} · {c.title}</h4>'
                f'<div class="meta">📅 {c.date} &nbsp;|&nbsp; 📍 {c.place} '
                f'&nbsp;|&nbsp; 📖 {c.source}</div>'
                f'<div class="body">{c.summary}</div>'
                f'<div class="body" style="margin-top:8px;color:#5C4A33;font-size:13.5px;">'
                f'<b>{T["original_excerpt"]}</b>: <em>{c.original_text}</em></div>'
                f'<div style="margin-top:10px;font-size:12.5px;">'
                f'<a href="{c.source_url}" target="_blank">{T["view_source"]}</a>'
                f'&nbsp;&nbsp;<span style="color:#8a7560;">📄 {c.license}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    if st.button(T["back_to_chat"], key="back_chat_bottom"):
        st.session_state.view = "chat"
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
# 사료 보관함 뷰 — 별도 페이지
# ─────────────────────────────────────────────────────────────
if st.session_state.view == "collection":
    render_collection_page()
    st.stop()


# ─────────────────────────────────────────────────────────────
# 빈 화면: 인사 + 추천 카드
# ─────────────────────────────────────────────────────────────
if not st.session_state.messages:
    greeting = GREETING_BY_LANG[st.session_state.language]
    st.markdown(
        f'<div class="greeting-card">'
        f'  <div class="greeting-char">{POINTING_SVG}</div>'
        f'  <div class="greeting-bubble">{greeting}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="suggest-section"><h5>{T["suggested_header"]}</h5></div>',
        unsafe_allow_html=True,
    )
    questions = SUGGESTED_QUESTIONS_BY_LANG[st.session_state.language]
    qcols = st.columns(len(questions))
    for i, q in enumerate(questions):
        with qcols[i]:
            char_svg = SUGGEST_CHARS[i % len(SUGGEST_CHARS)]
            st.markdown(
                f'<div class="suggest-char">{char_svg}</div>',
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
            f'<span class="thinking-char">{WALKING_SVG}</span>'
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
    "zh": "与你共同写就的、活着的实录。",
}
st.markdown(
    f'<div style="text-align:center;">'
    f'<div class="footer-strip">'
    f'  <div class="footer-char">{WALKING_SVG}</div>'
    f'  <div class="footer-text">{FOOTER_TAGLINE[st.session_state.language]}</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)
