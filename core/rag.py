"""사료 RAG 검색.

MVP 단계 단순 구현:
- 키워드·태그·인물·장소 매칭 기반 가중 점수
- 상위 k건 반환 (top-k=3)
- 임베딩 모드는 ENABLE_EMBEDDING=true 환경변수 시 활성화 (선택, 미구현)

본격 배포 시 Supabase pgvector 또는 ChromaDB로 교체.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_sillok.json"


@dataclass
class SourceCard:
    id: str
    title: str
    date: str
    source: str
    place: str
    place_coords: list[float]
    original_text: str
    summary: str
    easy_explanation: str
    tags: list[str]
    related_persons: list[str]
    source_url: str
    license: str
    score: float = 0.0
    # 디버그/시연용: 매칭된 토큰과 필드별 hit 정보
    matched_tokens: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "SourceCard":
        return cls(
            id=d["id"],
            title=d["title"],
            date=d["date"],
            source=d["source"],
            place=d["place"],
            place_coords=d.get("place_coords", []),
            original_text=d["original_text"],
            summary=d["summary"],
            easy_explanation=d.get("easy_explanation", ""),
            tags=d.get("tags", []),
            related_persons=d.get("related_persons", []),
            source_url=d.get("source_url", ""),
            license=d.get("license", ""),
        )


_CACHE: list[SourceCard] | None = None


def load_corpus(path: Path = DATA_PATH) -> list[SourceCard]:
    """샘플 사료 JSON을 로드해 SourceCard 리스트로 변환 (캐시 적용)."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    _CACHE = [SourceCard.from_dict(d) for d in data]
    return _CACHE


def reset_cache() -> None:
    """테스트·데이터 갱신 시 캐시 무효화."""
    global _CACHE
    _CACHE = None


# ──────────────────────────────────────────────────────────────
# 키워드 기반 검색 (MVP)
# ──────────────────────────────────────────────────────────────
_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")

# 검색 의미가 약한 한국어 불용어 (간이)
_STOPWORDS = {
    "그", "그것", "그게", "이것", "저것", "무엇", "뭔가", "어디", "어디서", "언제",
    "누가", "누구", "왜", "어떻게", "어떤", "있었", "있나", "있나요", "었나",
    "입니까", "인가", "인가요", "있었나", "있었던", "되었",
    "은", "는", "이", "가", "을", "를", "의", "에", "에서", "와", "과", "도",
    "the", "a", "an", "is", "was", "were", "are", "of", "in", "on", "at",
    "and", "or", "but", "to", "for", "with", "what", "who", "where", "when", "why", "how",
}


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _meaningful(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in _STOPWORDS and len(t) >= 2]


# 필드별 가중치 — title·tags·인물에 점수를 더 줌
_FIELD_WEIGHTS = {
    "title": 2.0,
    "tags": 1.8,
    "related_persons": 1.6,
    "place": 1.2,
    "summary": 1.0,
    "easy_explanation": 0.8,
    "date": 0.6,
}


def _field_text(card: SourceCard, field_name: str) -> str:
    if field_name == "tags":
        return " ".join(card.tags)
    if field_name == "related_persons":
        return " ".join(card.related_persons)
    return getattr(card, field_name, "")


def _score(card: SourceCard, query_tokens: list[str]) -> tuple[float, list[str]]:
    """가중 매칭 점수와 매칭된 토큰 목록을 함께 반환."""
    if not query_tokens:
        return 0.0, []

    score = 0.0
    matched: list[str] = []

    for field_name, weight in _FIELD_WEIGHTS.items():
        hay = _field_text(card, field_name).lower()
        if not hay:
            continue
        hay_tokens = set(_tokenize(hay))
        for qt in query_tokens:
            if qt in hay_tokens:
                score += weight
                matched.append(qt)
            else:
                # 부분 매칭 (한국어 형태소 미분리 보정) — 가중치는 절반
                for ht in hay_tokens:
                    if qt != ht and len(qt) >= 2 and (qt in ht or ht in qt):
                        score += weight * 0.4
                        matched.append(qt)
                        break

    # 중복 제거 후 정렬
    matched_unique = sorted(set(matched))
    return score, matched_unique


def search_corpus(
    query: str,
    top_k: int = 3,
    min_score: float = 0.6,
) -> list[SourceCard]:
    """질의 텍스트로 사료 검색.

    반환 결과의 score 필드에 매칭 점수, matched_tokens 필드에 매칭 토큰이 담긴다.
    min_score 미만은 잘라낸다. 너무 빡빡하면 빈 리스트가 되어 LLM이 '확인 불가'로 응답.
    """
    corpus = load_corpus()
    query_tokens = _meaningful(_tokenize(query))
    if not query_tokens:
        return []

    scored: list[SourceCard] = []
    for c in corpus:
        s, matched = _score(c, query_tokens)
        if s > 0:
            new = SourceCard(
                **{k: v for k, v in c.__dict__.items() if k not in ("score", "matched_tokens")},
                score=round(s, 3),
                matched_tokens=matched,
            )
            scored.append(new)

    scored.sort(key=lambda x: x.score, reverse=True)
    filtered = [c for c in scored if c.score >= min_score]
    return filtered[:top_k]


def search_by_tags(tags: Iterable[str], top_k: int = 3) -> list[SourceCard]:
    """태그 직접 매칭 (특정 미션 단서 등에 사용)."""
    corpus = load_corpus()
    tag_set = {t.lower() for t in tags}
    scored: list[SourceCard] = []
    for c in corpus:
        overlap = tag_set & {t.lower() for t in c.tags}
        if overlap:
            new = SourceCard(
                **{k: v for k, v in c.__dict__.items() if k not in ("score", "matched_tokens")},
                score=float(len(overlap)),
                matched_tokens=sorted(overlap),
            )
            scored.append(new)
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_k]
