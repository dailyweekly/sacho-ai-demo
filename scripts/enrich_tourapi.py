"""TourAPI 4.0 사이드카 enrichment — 모든 사료 카드에 주변 관광 명소 정보 부여.

실행:
    # 1) .env 에 TOURAPI_KEY_DECODED 입력 (한 번)
    # 2) 본 스크립트 1회 실행 — data/tour_enrichment.json 생성/갱신
    python -m scripts.enrich_tourapi
    # 또는 좌표가 있는 카드만 빠르게:
    python -m scripts.enrich_tourapi --radius 500 --max 3

출력 파일 ``data/tour_enrichment.json`` 은 커밋해서 Streamlit Cloud 에서는 키 없이
도 그대로 화면에 노출됨 (라이브 호출 없이 안정 시연).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# 패키지 외부 실행 지원
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import tourapi  # noqa: E402
from core.rag import load_corpus, DATA_PATH  # noqa: E402


OUT_PATH = DATA_PATH.parent / "tour_enrichment.json"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--radius", type=int, default=500,
                   help="주변 검색 반경 (m). 권장 300~800.")
    p.add_argument("--max", type=int, default=5,
                   help="카드당 저장할 최대 명소 수.")
    p.add_argument("--sleep", type=float, default=0.15,
                   help="API 호출 사이 sleep (초). data.go.kr 매너 콜.")
    p.add_argument("--force", action="store_true",
                   help="기존 enrichment 무시하고 전부 재호출.")
    args = p.parse_args()

    # 환경변수 로딩 — 로컬 .env 도 자동
    try:
        from core.rag import _safe_load_env  # type: ignore[attr-defined]
        _safe_load_env()
    except Exception:
        pass

    if not tourapi.is_enabled():
        print("[ERROR] TOURAPI_KEY_DECODED 환경변수가 비어 있습니다.\n"
              "        .env 파일에 TOURAPI_KEY_DECODED=... 입력 후 재실행.")
        return 2

    # 기존 enrichment 로드 (재실행 시 변경 없는 카드는 건너뜀)
    existing: dict[str, dict] = {}
    if OUT_PATH.exists() and not args.force:
        try:
            existing = json.loads(OUT_PATH.read_text("utf-8"))
        except Exception:
            existing = {}

    corpus = load_corpus()
    total = sum(1 for c in corpus if c.place_coords
                and len(c.place_coords) == 2)
    print(f"[INFO] 좌표 보유 카드 {total} 건 / 전체 {len(corpus)} 건")
    print(f"[INFO] 반경 {args.radius}m · 카드당 최대 {args.max}곳 · "
          f"sleep {args.sleep}s")

    enriched = dict(existing)
    hit, skip, miss, fail = 0, 0, 0, 0

    for c in corpus:
        if not c.place_coords or len(c.place_coords) != 2:
            continue
        if c.id in enriched and not args.force:
            skip += 1
            continue

        lon, lat = c.place_coords
        try:
            spots = tourapi.nearby_spots(
                lat=lat, lon=lon,
                radius_m=args.radius, num_rows=max(args.max * 2, 10),
            )
        except Exception as e:
            print(f"  [FAIL] {c.id}: {e}")
            fail += 1
            continue

        if not spots:
            miss += 1
            enriched[c.id] = {"radius_m": args.radius, "spots": []}
            continue

        # 가벼운 정제 — 라이선스/저장공간 최소화
        slim = [
            {
                "title": s["title"],
                "addr1": s.get("addr1", ""),
                "contentid": s.get("contentid", ""),
                "contenttypeid": s.get("contenttypeid", 0),
                "dist_m": s.get("dist_m"),
                # 썸네일 URL 만 저장 — 이미지는 KTO CDN
                "image": s.get("firstimage"),
            }
            for s in spots[: args.max]
        ]
        enriched[c.id] = {"radius_m": args.radius, "spots": slim}
        hit += 1
        print(f"  [HIT ] {c.id} · {c.place[:24]:<24} → "
              f"{len(slim)}곳 (top: {slim[0]['title']})")
        time.sleep(args.sleep)

    OUT_PATH.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print(f"[DONE] {OUT_PATH.relative_to(OUT_PATH.parents[1])} 저장")
    print(f"       hit={hit}  skip(cached)={skip}  no-nearby={miss}  fail={fail}")
    print(f"       총 {len(enriched)} 카드 enrichment")
    print()
    print("다음 단계:")
    print("  1) git add data/tour_enrichment.json && git commit -m 'TourAPI enrichment'")
    print("  2) git push → Streamlit Cloud 자동 재배포")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
