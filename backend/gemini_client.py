"""Gemini 호출 래퍼 — 자연어 쿼리를 필터 JSON으로 변환.

필터 스키마:
{
    "rsi": {"min": int | null, "max": int | null},
    "profit_growth_years": int | null,
    "is_leader": bool | null,
    "sector": str | null,
    "market_cap_trillion_min": number | null,
    "dividend_yield_min": number | null
}

Gemini 키가 없거나 호출이 실패하면 간단한 정규식 기반 로컬 파서로 폴백한다.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # 키 없을 때도 임포트 실패 방지

SYSTEM_PROMPT = """You are a filter extractor for a Korean stock screener.
Convert the user's natural language request into a JSON object with these optional keys:
- rsi: {min: integer 0-100, max: integer 0-100}
- profit_growth_years: integer (minimum consecutive years of operating profit growth)
- is_leader: boolean (true if user wants sector leader / 주도주 / 대장주)
- sector: string (one of 반도체, 자동차, 인터넷, 바이오, 2차전지, 금융, 화학, 철강, 통신, 건설, 유통, 엔터, 게임, 기타)
- market_cap_trillion_min: number (minimum market cap in trillion KRW)
- dividend_yield_min: number (minimum dividend yield in %)

Return ONLY a valid JSON object. Omit keys if not specified.
"""

KNOWN_SECTORS = [
    "반도체", "자동차", "인터넷", "바이오", "2차전지",
    "금융", "화학", "철강", "통신", "건설", "유통", "엔터", "게임",
]


def _local_parse(text: str) -> dict[str, Any]:
    filters: dict[str, Any] = {}

    m = re.search(r"RSI[^\d]*(\d{1,3})\s*[~\-–]\s*(\d{1,3})", text, re.IGNORECASE)
    if m:
        filters["rsi"] = {"min": int(m.group(1)), "max": int(m.group(2))}
    else:
        mi = re.search(r"RSI[^\d]*(\d{1,3})\s*이상", text, re.IGNORECASE)
        ma = re.search(r"RSI[^\d]*(\d{1,3})\s*이하", text, re.IGNORECASE)
        rsi_range: dict[str, int] = {}
        if mi:
            rsi_range["min"] = int(mi.group(1))
        if ma:
            rsi_range["max"] = int(ma.group(1))
        if rsi_range:
            filters["rsi"] = rsi_range

    pg = re.search(r"(\d+)\s*년.*(영업이익|이익)", text)
    if pg:
        filters["profit_growth_years"] = int(pg.group(1))

    if re.search(r"주도주|대장주", text):
        filters["is_leader"] = True

    for s in KNOWN_SECTORS:
        if s in text:
            filters["sector"] = s
            break

    cap = re.search(r"시총\s*(\d+(?:\.\d+)?)\s*조\s*이상", text)
    if cap:
        filters["market_cap_trillion_min"] = float(cap.group(1))

    div = re.search(r"배당\s*(?:수익률\s*)?(\d+(?:\.\d+)?)\s*%\s*이상", text)
    if div:
        filters["dividend_yield_min"] = float(div.group(1))

    return filters


def parse_query(text: str) -> dict[str, Any]:
    """Gemini로 파싱 시도 → 실패 시 로컬 폴백."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if api_key and genai is not None:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name,
                system_instruction=SYSTEM_PROMPT,
                generation_config={"response_mime_type": "application/json"},
            )
            resp = model.generate_content(text)
            raw = (resp.text or "").strip()
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception as e:  # noqa: BLE001
            # 로컬 폴백으로 조용히 내려감
            print(f"[gemini] parse failed, fallback to local: {e}")

    return _local_parse(text)
