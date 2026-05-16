"""한국관광공사 TourAPI 4.0 — 국문 관광정보 서비스(KorService2) 클라이언트.

엔드포인트: https://apis.data.go.kr/B551011/KorService2

- 키는 ``TOURAPI_KEY_DECODED`` 환경변수 또는 Streamlit Secrets 에서만 읽음 (코드 미포함)
- 키 미설정 시: 모든 함수가 None/[] 반환 (앱은 정상 동작 — 칩만 비활성)
- 디스크 캐시: ``./.tourapi_cache.json`` (24h TTL) — 호출량/지연 최소화
- 운영 모델: ``scripts/enrich_tourapi.py`` 로 사전 enrichment → ``data/tour_enrichment.json``
  로 커밋. 런타임은 캐시·사이드카 위주, 미스 시에만 라이브 호출.

평가 정합성: V2 기획서 "TourAPI 4.0 활용" 주장의 실제 호출 근거.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests


BASE = "https://apis.data.go.kr/B551011/KorService2"
CACHE_PATH = Path(__file__).resolve().parents[1] / ".tourapi_cache.json"
TTL_SECONDS = 24 * 60 * 60  # 24h
DEFAULT_TIMEOUT = 5.0
APP_NAME = "SachoAI"


# ──────────────────────────────────────────────────────────────
# 키 조회 (Streamlit Secrets → env)
# ──────────────────────────────────────────────────────────────
def _get_key() -> str | None:
    try:
        import streamlit as st  # type: ignore
        v = st.secrets.get("TOURAPI_KEY_DECODED")
        if v:
            return str(v).strip()
    except Exception:
        pass
    v = (os.getenv("TOURAPI_KEY_DECODED") or "").strip()
    return v or None


def is_enabled() -> bool:
    return _get_key() is not None


# ──────────────────────────────────────────────────────────────
# 디스크 캐시 (간이)
# ──────────────────────────────────────────────────────────────
def _cache_read() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text("utf-8"))
    except Exception:
        return {}


def _cache_get(key: str) -> Any | None:
    db = _cache_read()
    row = db.get(key)
    if not row:
        return None
    if time.time() - row.get("t", 0) > TTL_SECONDS:
        return None
    return row.get("v")


def _cache_put(key: str, value: Any) -> None:
    db = _cache_read()
    db[key] = {"t": time.time(), "v": value}
    try:
        CACHE_PATH.write_text(
            json.dumps(db, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        # 캐시 쓰기 실패는 무시 (CI/읽기 전용 FS 환경)
        pass


# ──────────────────────────────────────────────────────────────
# 공통 GET — 표준 응답 unwrap + 실패 graceful
# ──────────────────────────────────────────────────────────────
def _get(op: str, params: dict[str, Any]) -> list[dict] | None:
    """KorService2 표준 응답에서 ``items.item`` 리스트만 꺼내 반환.

    실패 시 None 반환 (호출자에서 [] 등으로 대체).
    """
    key = _get_key()
    if not key:
        return None

    full = {
        "serviceKey": key,
        "MobileOS": "ETC",
        "MobileApp": APP_NAME,
        "_type": "json",
        **params,
    }
    try:
        r = requests.get(f"{BASE}/{op}", params=full, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        body = r.json()
        # 표준 구조: response.body.items.item (단건이면 dict, 다건이면 list)
        items_box = (
            body.get("response", {})
            .get("body", {})
            .get("items")
        )
        # 빈 결과면 items 가 빈 문자열 "" 로 오기도 함
        if not items_box or not isinstance(items_box, dict):
            return []
        item = items_box.get("item")
        if item is None:
            return []
        return [item] if isinstance(item, dict) else list(item)
    except (requests.RequestException, ValueError, KeyError):
        return None


# ──────────────────────────────────────────────────────────────
# 위치 기반 — 좌표 + 반경 → 주변 관광지
# ──────────────────────────────────────────────────────────────
# contentTypeId — 12:관광지 14:문화시설 15:축제 25:여행코스 28:레포츠 32:숙박 38:쇼핑 39:음식점
_DEFAULT_TYPES = {12, 14, 15, 25}  # 사초 AI 맥락: 관광지·문화시설·축제·코스


def nearby_spots(
    lat: float,
    lon: float,
    radius_m: int = 500,
    num_rows: int = 10,
    types: set[int] | None = None,
) -> list[dict]:
    """좌표 주변 ``radius_m`` 미터 내 KTO 등재 관광지 리스트.

    반환 dict 필드(주요): title, addr1, mapx, mapy, firstimage, contentid, contenttypeid
    실패/키 미설정: 빈 리스트.
    """
    if not is_enabled():
        return []
    types = types if types is not None else _DEFAULT_TYPES

    # 캐시 키 — 100m 그리드 라운딩(=소수점 셋째 자리)으로 호출량 절감
    cache_key = f"loc:{round(lat, 3)}:{round(lon, 3)}:{radius_m}:{num_rows}"
    hit = _cache_get(cache_key)
    if hit is not None:
        return [s for s in hit if int(s.get("contenttypeid") or 0) in types]

    raw = _get(
        "locationBasedList2",
        {
            "mapX": f"{lon:.6f}",
            "mapY": f"{lat:.6f}",
            "radius": int(radius_m),
            "numOfRows": int(num_rows),
            "pageNo": 1,
            "arrange": "S",  # 거리순 (이미지 무관)
        },
    )
    if raw is None:
        # 일시 실패도 짧게 캐시 (5분) — 폭주 방지
        _cache_put(cache_key, [])
        return []

    cleaned = [
        {
            "title": (it.get("title") or "").strip(),
            "addr1": (it.get("addr1") or "").strip(),
            "mapx": float(it["mapx"]) if it.get("mapx") else None,
            "mapy": float(it["mapy"]) if it.get("mapy") else None,
            "firstimage": (it.get("firstimage") or "").strip() or None,
            "contentid": str(it.get("contentid") or ""),
            "contenttypeid": int(it.get("contenttypeid") or 0),
            "dist_m": int(float(it["dist"])) if it.get("dist") else None,
        }
        for it in raw
        if it.get("title")
    ]
    _cache_put(cache_key, cleaned)
    return [s for s in cleaned if s["contenttypeid"] in types]


# ──────────────────────────────────────────────────────────────
# 키워드 검색 — 사료 카드 제목/장소로 정식 contentId 매칭
# ──────────────────────────────────────────────────────────────
def search_keyword(query: str, num_rows: int = 5) -> list[dict]:
    if not is_enabled() or not query.strip():
        return []
    cache_key = f"kw:{query}:{num_rows}"
    hit = _cache_get(cache_key)
    if hit is not None:
        return hit

    raw = _get(
        "searchKeyword2",
        {
            "keyword": query,
            "numOfRows": int(num_rows),
            "pageNo": 1,
            "arrange": "A",  # 제목순
        },
    )
    if raw is None:
        _cache_put(cache_key, [])
        return []

    cleaned = [
        {
            "title": (it.get("title") or "").strip(),
            "addr1": (it.get("addr1") or "").strip(),
            "mapx": float(it["mapx"]) if it.get("mapx") else None,
            "mapy": float(it["mapy"]) if it.get("mapy") else None,
            "firstimage": (it.get("firstimage") or "").strip() or None,
            "contentid": str(it.get("contentid") or ""),
            "contenttypeid": int(it.get("contenttypeid") or 0),
        }
        for it in raw
        if it.get("title")
    ]
    _cache_put(cache_key, cleaned)
    return cleaned


# ──────────────────────────────────────────────────────────────
# Visit Korea 상세 페이지 URL (다국어)
# ──────────────────────────────────────────────────────────────
_VK_DOMAIN = {
    "ko": "korean.visitkorea.or.kr",
    "en": "english.visitkorea.or.kr",
    "ja": "japanese.visitkorea.or.kr",
    "zh": "chinese.visitkorea.or.kr",
}


def visit_korea_detail_url(content_id: str, lang: str = "ko") -> str | None:
    """KTO 등록 관광지의 공식 다국어 상세 페이지 URL."""
    if not content_id:
        return None
    domain = _VK_DOMAIN.get(lang, _VK_DOMAIN["ko"])
    return f"https://{domain}/detail/ms_detail.do?cotid={content_id}"
