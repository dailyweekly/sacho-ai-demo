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
from core.rag import search_corpus, SourceCard, load_corpus
from core.badge import parse_response, render_badge_html, sanitize_streaming_text
from core.prompts import GREETING_BY_LANG, SUGGESTED_QUESTIONS_BY_LANG, UI_TEXT
from core.character import (
    LOGO_SVG, LOCK_SVG, char_img,
)
from core.quest import (
    generate_question, pick_card, QUEST_THEME_KEYWORDS,
    COURSES, course_card_count, pick_course_card, ending_tier,
)
import random as _random


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
        padding: 1rem 2rem 1.5rem 2rem;
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
        background: #FBF7F2;
        border: 2.5px solid var(--ink);
        border-radius: 22px;
        box-shadow: 4px 4px 0 var(--ink);
        margin: 4px 0 22px 0;
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
    }
    .topbar-logo .logo-svg { animation: bob 4s ease-in-out infinite; }
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

    /* 문제 카드 */
    .quest-q {
        display: flex; gap: 14px; align-items: flex-start;
        background: #FFFCF0;
        border: 2.5px solid var(--ink);
        border-radius: 18px;
        padding: 18px 20px;
        margin-bottom: 14px;
        box-shadow: 4px 4px 0 var(--ink);
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
    }
    .quest-q-body {
        flex: 1;
        font-family: 'Gowun Batang', serif;
        font-size: 17px;
        line-height: 1.7;
        color: var(--ink);
    }

    /* 결과 띠 */
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

    /* 코스 진행 표시 */
    .course-progress {
        background: #FFF7DA;
        border: 1.5px dashed var(--ink);
        border-radius: 12px;
        padding: 8px 14px;
        font-family: 'Gowun Batang', serif;
        font-size: 13.5px;
        color: var(--ink);
        margin-bottom: 12px;
    }
    .course-progress b { color: var(--red-deep); }

    /* 힌트 영역 */
    .hint-tag {
        font-family: 'Gowun Batang', serif;
        font-size: 13px;
        padding: 9px 14px;
        border-radius: 12px;
        border: 1.5px dashed var(--ink-soft);
        text-align: center;
        margin: 0;
    }
    .hint-used-tag {
        background: #DDF0CB;
        color: #2E6418;
        border-color: #2E6418;
    }
    .hint-locked-tag {
        background: #F0EDE6;
        color: var(--ink-soft);
    }

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
        flex: 0 0 130px;
        animation: float-y 4s ease-in-out infinite;
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
    @media (max-width: 720px) {
        .quest-ending { flex-direction: column; text-align: center; }
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
    .evidence-card .license-tag {
        margin-top: 6px;
        font-size: 11.5px;
        color: #8a7560;
        font-family: 'Noto Sans KR', sans-serif;
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

    /* ─── 🔐 비밀번호 게이트 (초 귀엽게) ─── */
    .gate-wrap {
        display: flex; justify-content: center;
        padding: 36px 12px 60px 12px;
    }
    .gate-card {
        width: 100%; max-width: 520px;
        background: #FBF7F2;     /* 캐릭터 PNG 배경과 동일한 베이지 */
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
    /* 게이트 안쪽 Why + How-to-play */
    .gate-why {
        margin-top: 22px;
        padding-top: 18px;
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

    # 게이트 페이지만 바깥은 흰색 (캐릭터 박스만 베이지로 보이도록)
    st.markdown(
        '<style>'
        '.stApp { background: #FFFFFF !important; }'
        '.stApp::before, .stApp::after { display: none; }'
        '</style>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="gate-wrap">'
        f'<div class="gate-card{shake_class}">'
        f'  <div class="gate-chars">'
        f'    <div class="char-main">{char_img("whodat", width=170)}</div>'
        f'    <div class="char-lock">{LOCK_SVG}</div>'
        f'  </div>'
        f'  <div class="gate-bubble">'
        f'    어어… <b>누구세요…?</b><br>'
        f'    사관 두루마리 방탈출에 들어오시려면 암호를 살짝 속삭여 주시구려.'
        f'    <small>(Korean-history quest game. Whisper the password to enter.)</small>'
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

    # ── 왜 사초 AI? + 어떻게 노나요 (게이트 안쪽) ──
    st.markdown(
        '<div class="gate-why">'
        '  <div class="gate-why-head">'
        '    <span class="gate-why-title">✨ 왜 사초 AI?</span>'
        '    <span class="gate-why-sub">— 한국사 사료 검증형 퀴즈 게임 —</span>'
        '  </div>'
        '  <div class="gate-why-grid">'
        '    <div class="gate-why-cell"><b>🎮 매번 새 문제</b>'
        '      <p>AI가 90건의 사료에서 매번 다르게 출제합니다. 한 번 풀고 끝나는 게임이 아닙니다.</p></div>'
        '    <div class="gate-why-cell"><b>🗺 관광지·세부 위치까지</b>'
        '      <p>경복궁·경주 첨성대·단양 도담삼봉. 지도 핀·사진과 함께 그 자리의 역사를 즉시.</p></div>'
        '    <div class="gate-why-cell"><b>🔍 답변마다 원문 링크</b>'
        '      <p>조선왕조실록·고려사·한국사DB 1차 사료를 클릭해 직접 확인. 출처 없는 답변은 없습니다.</p></div>'
        '    <div class="gate-why-cell"><b>⚖ 학설은 양면 + 4개 국어</b>'
        '      <p>견해가 갈리는 사안은 한쪽으로 단정하지 않고 양측을 함께. 한·영·일·중 동시 지원.</p></div>'
        '  </div>'
        '  <div class="gate-howto">'
        '    <b>🎯 노는 법</b>'
        '    <ol>'
        '      <li>주제(서울 궁궐 · 경주 · 단양 · 일제강점기 등) 고르기</li>'
        '      <li>사관이 4지선다 문제를 출제 → 한 줄 골라 답하기</li>'
        '      <li>맞으면 +10 사초, 틀려도 상세 해설 + 사료 + 지도 보여드림</li>'
        '      <li>연속 정답 = 연승, 누적 사초 = 자랑할 거리</li>'
        '    </ol>'
        '  </div>'
        '</div>'
        '<div class="gate-foot">— 졸린 사관이 지키는 두루마리 방 —</div>'
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


# 여백 데코 캐릭터는 답변 중에도 거슬려서 제거


# ─────────────────────────────────────────────────────────────
# 가로형 톱바
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="topbar-tools">', unsafe_allow_html=True)

bar_cols = st.columns([2.0, 1.2, 1.0, 1.0, 1.0, 0.7, 0.7])

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
        st.session_state.language = lang_options[lang_label]
        st.session_state.messages = []
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
title, subtitle = HEADER_TEXT[st.session_state.language]
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
    """장소 좌표 + 제목으로 지도·사진 검색 링크 생성."""
    import urllib.parse as up
    bits = []
    title_q = up.quote(c.title.split("—")[0].strip())
    place_q = up.quote(c.place.split("(")[0].strip())
    # Google Maps — 좌표가 있으면 좌표 핀, 없으면 장소명 검색
    if c.place_coords and len(c.place_coords) == 2:
        lon, lat = c.place_coords
        gmap = f"https://www.google.com/maps?q={lat},{lon}({title_q})"
    else:
        gmap = f"https://www.google.com/maps/search/{title_q}"
    bits.append(
        f'<a class="place-link" href="{gmap}" target="_blank" rel="noopener">'
        f'{T["map_open"]}</a>'
    )
    # 네이버 이미지 검색 (한국어 검색이 풍부)
    img = f"https://search.naver.com/search.naver?where=image&query={place_q}"
    bits.append(
        f'<a class="place-link" href="{img}" target="_blank" rel="noopener">'
        f'{T["photo_search"]}</a>'
    )
    return " ".join(bits)


def render_evidence_cards(cards: list[SourceCard]) -> None:
    if not cards:
        return
    st.markdown(f"##### {T['evidence_header']}")
    for c in cards:
        authority = _source_authority(c.source_url)
        st.markdown(
            f'<div class="evidence-card">'
            f'<h4>📜 {T["evidence_id"]} <code>{c.id}</code> · {c.title}</h4>'
            f'<div class="meta">📅 {c.date} &nbsp;|&nbsp; 📍 {c.place} '
            f'&nbsp;|&nbsp; 📖 {c.source}</div>'
            f'<div class="body">{c.summary}</div>'
            f'<div class="body" style="margin-top:8px;color:#5C4A33;font-size:13.5px;">'
            f'<b>{T["original_excerpt"]}</b>: <em>{c.original_text}</em></div>'
            f'<div class="place-row">{_place_links(c)}</div>'
            f'<div class="verify-row">'
            f'<a class="verify-btn" href="{c.source_url}" target="_blank" '
            f'rel="noopener">🔍 {T["view_source"]}</a>'
            f'<span class="source-authority">{authority}</span>'
            f'</div>'
            f'<div class="license-tag">📄 {c.license}</div>'
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
    """주어진 카드로 문제를 생성해 세션에 저장 (스피너 포함)."""
    with st.spinner(T["quest_thinking"]):
        new_q = generate_question(
            card,
            language=st.session_state.language,
            mode=st.session_state.mode,
        )
    st.session_state.current_q = new_q
    st.session_state.q_answered = False
    st.session_state.q_user_choice = None
    st.session_state.eliminated_options = []
    st.session_state.q_seen_ids.append(card.id)


def render_quest_page() -> None:
    # ── 코스 종료 화면 ──
    if st.session_state.course_finished:
        cid = st.session_state.course_id
        total = course_card_count(cid)
        score = st.session_state.course_score
        tier = ending_tier(score, total)
        tier_msg = T.get(f"ending_{tier}", T["ending_apprentice"])
        char_pose = {
            "master":     "celebrate",
            "companion":  "happy",
            "apprentice": "careful_write",
            "novice":     "facedown",
        }.get(tier, "careful_write")

        st.markdown(
            f'<div class="quest-ending">'
            f'  <div class="ending-char">{char_img(char_pose, width=130)}</div>'
            f'  <div class="ending-text">'
            f'    <h3>{T["ending_title"]}</h3>'
            f'    <p class="ending-score">'
            f'{T["ending_score_line"].format(score=score, total=total)}</p>'
            f'    <p class="ending-tier">{tier_msg}</p>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button(T["ending_restart_btn"], key="ending_restart",
                     use_container_width=True):
            st.session_state.course_finished = False
            st.session_state.course_idx = 0
            st.session_state.course_score = 0
            _reset_question_state()
            st.rerun()
        return

    _credit_bar()

    q = st.session_state.current_q

    # ── 문제 없을 때 — 모드/주제 선택 + 시작 ──
    if q is None:
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

        # 놀이 방식 선택 (라디오 — 코스 vs 자유 테마)
        play_modes = {
            T["play_mode_course"]: "course",
            T["play_mode_theme"]:  "theme",
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

        # 코스 / 테마 셀렉트
        col_a, col_b = st.columns([3, 2])
        with col_a:
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

        with col_b:
            st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)
            if st.button(T["quest_start_btn"], key="quest_start", use_container_width=True):
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
    # 코스 진행 표시
    if st.session_state.play_mode == "course":
        cid = st.session_state.course_id
        total = course_card_count(cid)
        idx_show = st.session_state.course_idx + 1
        course_name = _course_options()[cid]
        st.markdown(
            f'<div class="course-progress">'
            f'<b>🗺 {course_name}</b> · '
            f'{T["course_progress"].format(n=idx_show, total=total)} · '
            f'{T["course_score"]}: <b>{st.session_state.course_score}/{idx_show - 1 if not st.session_state.q_answered else idx_show}</b>'
            f'</div>',
            unsafe_allow_html=True,
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

    # ── 답변 전 — 힌트 + 4지선다 ──
    if not answered:
        # 힌트 행
        hint_col_l, hint_col_r = st.columns([1, 1])
        with hint_col_l:
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

        # 4지선다 버튼 (힌트로 제외된 것은 비활성)
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
                is_correct = (i == q["correct_idx"])
                if is_correct:
                    st.session_state.credits += 10
                    st.session_state.streak += 1
                    st.session_state.total_correct += 1
                    if st.session_state.streak > st.session_state.best_streak:
                        st.session_state.best_streak = st.session_state.streak
                else:
                    st.session_state.streak = 0
                # 코스 점수
                if st.session_state.play_mode == "course" and is_correct:
                    st.session_state.course_score += 1
                st.rerun()
        return

    # ── 답변 후 — 결과 + 선지 회고 + 옵션 노트 + 해설 + 사료 + 지도 ──
    user = st.session_state.q_user_choice
    correct = q["correct_idx"]
    if user == correct:
        st.markdown(
            f'<div class="quest-result correct">{T["quest_correct"]}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="quest-result wrong">{T["quest_wrong"]} '
            f'<b>{marks[correct]} {q["options"][correct]}</b></div>',
            unsafe_allow_html=True,
        )

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
    if st.button(T["quest_next_btn"], key="quest_next", use_container_width=True):
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
    "zh": "与你共同写就的、活着的实录。",
}
st.markdown(
    f'<div style="text-align:center;">'
    f'<div class="footer-strip">'
    f'  <div class="footer-char">{char_img("cheer", width=58)}</div>'
    f'  <div class="footer-text">{FOOTER_TAGLINE[st.session_state.language]}</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)
