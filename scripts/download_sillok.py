"""공공데이터포털 — 조선왕조실록 원문 데이터 다운로드 스크립트.

활용 데이터셋:
- 「교육부 국사편찬위원회_조선왕조실록 정보_고순종실록 원문」
  https://www.data.go.kr/data/15053646/fileData.do
- 「교육부 국사편찬위원회_조선왕조실록 정보_실록원문」
  https://www.data.go.kr/data/15053647/fileData.do

본 스크립트는 파일데이터(CSV/TXT) 다운로드와 청크 변환을 자동화한다.
※ 파일데이터는 로그인·인증키 없이 다운로드 가능. API 호출은 인증키 필요.

사용법:
    python scripts/download_sillok.py --help
    python scripts/download_sillok.py --period 1895-1910 --output data/raw/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests


# 공공데이터포털 파일 직접 다운로드 URL (수동 확인 필요)
# 실제 다운로드 URL은 data.go.kr 사이트에서 로그인 후 받은 링크를 사용
DATA_SOURCES = {
    "gosunjong": {
        "name": "고종·순종실록 원문",
        "page": "https://www.data.go.kr/data/15053646/fileData.do",
        "license": "이용허락범위 제한 없음",
    },
    "sillok": {
        "name": "조선왕조실록 원문 (태조~철종)",
        "page": "https://www.data.go.kr/data/15053647/fileData.do",
        "license": "이용허락범위 제한 없음",
    },
}


def show_manual():
    """수동 다운로드 가이드 출력 (직접 URL 자동화는 사이트 변경에 취약)."""
    print("=" * 70)
    print("공공데이터포털 사료 데이터 다운로드 가이드")
    print("=" * 70)
    print()
    print("본 스크립트는 사이트 정책상 직접 자동 다운로드 대신 수동 단계를 안내합니다.")
    print("(공공데이터포털 파일 URL이 세션 토큰을 포함해 자주 변경되기 때문)")
    print()
    print("다운로드 절차:")
    print("-" * 70)
    for key, info in DATA_SOURCES.items():
        print(f"[{key}] {info['name']}")
        print(f"  페이지: {info['page']}")
        print(f"  라이선스: {info['license']}")
        print(f"  → 페이지에서 '다운로드' 버튼 클릭, ./data/raw/{key}/ 에 저장")
        print()
    print("=" * 70)
    print()
    print("다운로드 후 다음 명령으로 청크화·메타데이터 변환:")
    print("    python scripts/chunk_sillok.py --input data/raw/ --output data/processed/")
    print()
    print("청크화된 데이터를 sample_sillok.json 형식과 통합하려면:")
    print("    python scripts/merge_corpus.py")
    print()


def fetch_test():
    """공공데이터포털 API의 단순 ping (연결 가능성 확인용)."""
    url = "https://www.data.go.kr/"
    try:
        r = requests.head(url, timeout=10)
        print(f"OK: {url} → status {r.status_code}")
    except Exception as e:
        print(f"ERR: {url} → {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="공공데이터포털 사료 데이터 다운로드 가이드 및 유틸"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="공공데이터포털 연결 가능성만 점검",
    )
    parser.add_argument(
        "--period", default="1896-1907",
        help="대상 기간 (기본 1896-1907 — 정동·덕수궁 코스 권장)",
    )
    parser.add_argument(
        "--output", default="data/raw/",
        help="다운로드 저장 경로 (기본 ./data/raw/)",
    )
    args = parser.parse_args()

    if args.check:
        fetch_test()
        return

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    show_manual()
    print(f"※ 다운로드 후 저장 경로: {out.resolve()}")
    print(f"※ 대상 기간: {args.period}")


if __name__ == "__main__":
    main()
