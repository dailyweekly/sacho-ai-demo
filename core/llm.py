"""Claude API 호출 래퍼.

- 스트리밍 응답 지원
- 시스템 프롬프트(모드별) + RAG 컨텍스트 + 대화이력 자동 결합
- API 키는 환경변수 ANTHROPIC_API_KEY 또는 .env에서 로드
- 일시적 네트워크/Rate Limit 오류 시 지수 백오프 재시도
- 응답 완료 시 usage(input/output 토큰)를 콜백으로 노출
"""
from __future__ import annotations

import os
import time
from typing import Callable, Iterator, Optional

from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError

from core.prompts import get_system_prompt
from core.rag import SourceCard


DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_MAX_TOKENS = 800
DEFAULT_TEMPERATURE = 0.6

# Anthropic 공식 가격 (USD per 1M tokens, Sonnet 4.5 기준)
PRICE_INPUT_USD_PER_MTOK = 3.0
PRICE_OUTPUT_USD_PER_MTOK = 15.0
USD_TO_KRW = 1380  # 시연용 고정 환율 (실제는 시세 적용 필요)


def get_client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. "
            "프로젝트 루트의 .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하거나, "
            "환경변수로 설정하세요."
        )
    return Anthropic(api_key=api_key)


def _build_rag_context(cards: list[SourceCard], mode: str = "일반") -> str:
    """RAG로 검색된 사료를 LLM이 인용 가능한 형식으로 정리.

    가족 모드는 easy_explanation을 우선 노출한다.
    """
    if not cards:
        return "(관련 사료가 검색되지 않았습니다. '확인 불가' 또는 '추정'으로 응답하세요.)"
    family = mode.startswith("가족") if mode else False
    lines = ["## 관련 사료 (RAG 검색 결과)"]
    for c in cards:
        primary = c.easy_explanation if family and c.easy_explanation else c.summary
        secondary = c.summary if family and c.easy_explanation else c.easy_explanation
        block = [
            f"- **{c.id}** | {c.date} | {c.title}",
            f"  - 출처: {c.source}",
            f"  - 장소: {c.place}",
            f"  - 요약: {primary}",
            f"  - 원문 발췌: {c.original_text}",
        ]
        if secondary:
            block.append(f"  - 부가 설명: {secondary}")
        lines.append("\n".join(block))
    return "\n\n".join(lines)


def build_user_message(
    query: str,
    cards: list[SourceCard],
    language: str = "ko",
    mode: str = "일반",
) -> str:
    """LLM에 전달할 사용자 메시지 — 질의 + RAG 컨텍스트 + 언어·모드 지시."""
    lang_map = {
        "ko": "한국어",
        "en": "English",
        "ja": "日本語",
        "zh": "中文 (简体)",
    }
    lang_name = lang_map.get(language, "한국어")
    mode_hint = ""
    if mode and mode.startswith("가족"):
        mode_hint = "응답 톤은 만 8세 이상 가족 모드 가이드(짧은 문장·쉬운 어휘)를 따르십시오."
    return (
        f"{_build_rag_context(cards, mode)}\n\n"
        f"## 사용자 질문\n{query}\n\n"
        f"## 응답 언어\n위 사료에 근거하여 **{lang_name}**로 응답하세요. "
        f"응답 형식(```badge``` 블록 + 본문)을 반드시 지키십시오. {mode_hint}"
    )


def _is_transient(err: BaseException) -> bool:
    if isinstance(err, (APIConnectionError, RateLimitError)):
        return True
    if isinstance(err, APIError):
        status = getattr(err, "status_code", None)
        if status is not None and 500 <= status < 600:
            return True
    return False


def stream_sagwan_response(
    query: str,
    cards: list[SourceCard],
    history: list[dict] | None = None,
    language: str = "ko",
    mode: str = "일반",
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    on_complete: Optional[Callable[[dict], None]] = None,
    max_retries: int = 2,
) -> Iterator[str]:
    """사관 응답을 스트리밍 형태로 반환.

    Args:
        on_complete: 스트림 종료 시 usage 정보(dict)를 받는 콜백.
            keys: input_tokens, output_tokens, model, stop_reason, est_cost_usd, est_cost_krw
        max_retries: 일시적 오류(429/5xx/네트워크)에 대한 최대 재시도 횟수.

    Yields:
        부분 텍스트 청크. 호출자는 이어붙여 최종 응답을 구성한다.
    """
    client = get_client()
    user_msg = build_user_message(query, cards, language, mode)
    system_prompt = get_system_prompt(mode)

    messages: list[dict] = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_msg})

    attempt = 0
    while True:
        try:
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for chunk in stream.text_stream:
                    yield chunk
                if on_complete is not None:
                    try:
                        final = stream.get_final_message()
                        in_tok = getattr(final.usage, "input_tokens", 0)
                        out_tok = getattr(final.usage, "output_tokens", 0)
                        cost_usd = (
                            in_tok / 1_000_000 * PRICE_INPUT_USD_PER_MTOK
                            + out_tok / 1_000_000 * PRICE_OUTPUT_USD_PER_MTOK
                        )
                        on_complete({
                            "input_tokens": in_tok,
                            "output_tokens": out_tok,
                            "model": getattr(final, "model", model),
                            "stop_reason": getattr(final, "stop_reason", None),
                            "est_cost_usd": round(cost_usd, 6),
                            "est_cost_krw": round(cost_usd * USD_TO_KRW, 2),
                        })
                    except Exception:
                        # usage 산출 실패는 본 응답을 막지 않음
                        pass
            return
        except Exception as err:
            if attempt < max_retries and _is_transient(err):
                # 지수 백오프: 0.6s → 1.5s
                time.sleep(0.6 * (2 ** attempt))
                attempt += 1
                continue
            raise


def complete_sagwan_response(
    query: str,
    cards: list[SourceCard],
    history: list[dict] | None = None,
    language: str = "ko",
    mode: str = "일반",
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """비-스트리밍 1회 응답 (배치 처리·평가셋 실행용)."""
    return "".join(
        stream_sagwan_response(
            query=query,
            cards=cards,
            history=history,
            language=language,
            mode=mode,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    )
