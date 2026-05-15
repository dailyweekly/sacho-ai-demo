# scripts/ — 데이터 처리 스크립트

## `download_sillok.py` — 공공데이터포털 사료 다운로드 가이드

```bash
# 연결 점검
python scripts/download_sillok.py --check

# 다운로드 가이드 + 저장 경로 안내
python scripts/download_sillok.py --period 1896-1907 --output data/raw/
```

> 공공데이터포털 파일은 직접 페이지에서 '다운로드' 버튼으로 받습니다. 본 스크립트는 페이지 URL과 저장 경로를 안내합니다.

## 향후 추가 예정 스크립트 (Phase 1 사업화 단계)

| 스크립트 | 역할 | 상태 |
|---|---|---|
| `chunk_sillok.py` | 다운로드 원문을 [날짜·인물·장소] 단위로 청크화 + 메타데이터 보존 | TODO |
| `embed_corpus.py` | OpenAI text-embedding-3-large 또는 BGE-Korean으로 임베딩 | TODO |
| `merge_corpus.py` | 샘플 10건과 청크 다운로드 데이터 통합 | TODO |
| `evaluate_rag.py` | 정답 가능 / 근접 오답 / 답변 불가 / 다국어 / 적대 50문항 평가셋 실행 | TODO |

## 데이터 라이선스

`sample_sillok.json`의 `license` 필드를 반드시 확인하세요. 공공데이터포털 데이터는 "이용허락범위 제한 없음"이지만, 한국사데이터베이스 웹페이지의 번역문·해제 등은 별도 라이선스가 적용됩니다 — 상업적 활용 전 국사편찬위원회에 사전 문의가 필요합니다.
