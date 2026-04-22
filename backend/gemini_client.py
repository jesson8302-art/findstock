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
- sector: string (one of 반도체, 자동차, 2차전지, 인터넷, 바이오, 금융, 화학, 철강, 통신, 건설, 유통, 엔터, 게임, 방산, 조선, 기계장비, 에너지, 음식료, 의료기기, 소프트웨어, 의류패션, 운송물류, 부동산, 기타)
- market_cap_trillion_min: number (minimum market cap in trillion KRW)
- dividend_yield_min: number (minimum dividend yield in %)
- change_pct_min: number (minimum daily price change %, e.g. 5 means stocks up 5% or more, 20 means up 20%+)
- change_pct_max: number (maximum daily price change %)
- target_date: string YYYY-MM-DD (convert Korean date expressions to this format, current year is 2026. Examples: "4월6일"→"2026-04-06", "4/21"→"2026-04-21", "어제"→yesterday's date)

Return ONLY a valid JSON object. Omit keys if not specified.
"""

KNOWN_SECTORS = [
    "반도체", "자동차", "인터넷", "바이오", "2차전지",
    "금융", "화학", "철강", "통신", "건설", "유통", "엔터", "게임",
]


def _parse_korean_date(text: str) -> str | None:
    """한국어 날짜 표현을 YYYY-MM-DD 로 변환."""
    from datetime import date, timedelta
    today = date.today()
    year = today.year

    # "어제"
    if "어제" in text:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # "4/21", "4-21"
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year}-{month:02d}-{day:02d}"

    # "4월21일", "4월 21일"
    m = re.search(r"(\d{1,2})월\s*(\d{1,2})일", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        return f"{year}-{month:02d}-{day:02d}"

    return None


def _local_parse(text: str) -> dict[str, Any]:
    filters: dict[str, Any] = {}

    # RSI
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

    # 날짜
    target_date = _parse_korean_date(text)
    if target_date:
        filters["target_date"] = target_date

    # 등락률 범위: "20~25% 상승", "20~25%"
    m = re.search(r"(\d+(?:\.\d+)?)\s*[~\-–]\s*(\d+(?:\.\d+)?)\s*%", text)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        # 상승/하락 방향 판단
        if "하락" in text or "하방" in text or "떨어" in text:
            filters["change_pct_min"] = -hi
            filters["change_pct_max"] = -lo
        else:
            filters["change_pct_min"] = lo
            filters["change_pct_max"] = hi
    else:
        # "5% 이상 상승"
        m_up = re.search(r"(\d+(?:\.\d+)?)\s*%\s*이상\s*(?:상승|올|급등)?", text)
        if m_up and "하락" not in text:
            filters["change_pct_min"] = float(m_up.group(1))
        m_dn = re.search(r"(\d+(?:\.\d+)?)\s*%\s*이상\s*(?:하락|떨어|급락)?", text)
        if m_dn and "하락" in text:
            filters["change_pct_min"] = -float(m_dn.group(1))

    # 연속 성장
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
