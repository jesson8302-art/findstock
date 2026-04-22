"""FastAPI 프록시 서버.

프론트는 /api/* 만 호출하고, 여기서 Supabase / Gemini / 필터링을 모두 처리한다.

엔드포인트:
  GET  /api/stocks                → 종목 리스트(지표 + 시총 + 배당 포함)
  GET  /api/stocks/{code}/history → 해당 종목 일별 시세
  GET  /api/indices               → KOSPI/KOSDAQ/KRX300 최신 지수
  GET  /api/commodities           → 금/원유/구리 최신 시세
  POST /api/parse-query           → 자연어 → 필터 JSON
  POST /api/search                → 파싱 + 필터링을 서버사이드에서 한번에

Supabase 설정이 없으면 내장 mock 데이터를 서빙한다.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from gemini_client import parse_query as gemini_parse

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# 백엔드는 서버사이드이므로 service role 키 우선 사용 (RLS 우회)
SUPABASE_ANON_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv(
    "SUPABASE_ANON_KEY", ""
)


def _supabase_or_none():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None
    try:
        from supabase import create_client

        return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception as e:  # noqa: BLE001
        print(f"[supabase] init failed: {e}")
        return None


# --- 폴백용 mock (프론트의 mockStocks.js와 동일한 구조) -------------------

_MOCK_STOCKS: list[dict[str, Any]] = [
    {
        "code": "005930", "name": "삼성전자", "sector": "반도체",
        "is_leader": False, "leader_name": "SK하이닉스",
        "buy_score": 74, "rsi": 68, "rsi_prev": 48, "profit_growth_years": 3,
        "price": 72500, "change": 1.2,
        "financials": {"revenue": "302.2조", "profit": "35.8조", "roe": "12.5%",
                       "desc": "메모리 업황 회복세가 뚜렷하며 3년 연속 영업이익 우상향 기조 유지 중."},
    },
    {
        "code": "000660", "name": "SK하이닉스", "sector": "반도체",
        "is_leader": True, "leader_name": "SK하이닉스",
        "buy_score": 95, "rsi": 72, "rsi_prev": 60, "profit_growth_years": 1,
        "price": 185000, "change": -0.5,
        "financials": {"revenue": "45.1조", "profit": "8.2조", "roe": "15.1%",
                       "desc": "HBM 시장 독점적 지위 확보로 섹터 내 가장 강력한 주도주 모멘텀 보유."},
    },
    {
        "code": "005380", "name": "현대차", "sector": "자동차",
        "is_leader": True, "leader_name": "현대차",
        "buy_score": 88, "rsi": 58, "rsi_prev": 45, "profit_growth_years": 4,
        "price": 250000, "change": 2.1,
        "financials": {"revenue": "162.7조", "profit": "15.1조", "roe": "10.8%",
                       "desc": "하이브리드 및 전기차 믹스 개선으로 역대 최대 실적 경신 중."},
    },
    {
        "code": "035420", "name": "NAVER", "sector": "인터넷",
        "is_leader": False, "leader_name": "카카오",
        "buy_score": 62, "rsi": 45, "rsi_prev": 42, "profit_growth_years": 2,
        "price": 192000, "change": 0.5,
        "financials": {"revenue": "9.6조", "profit": "1.4조", "roe": "8.2%",
                       "desc": "광고 및 커머스 성장세는 안정적이나 신사업 투자 비용 증가 추세."},
    },
]


def _generate_mock_history(base_price: float, count: int = 150) -> list[dict[str, Any]]:
    import random

    out = []
    price = base_price
    for i in range(count):
        change = (random.random() - 0.5) * 0.04
        o = price
        c = price * (1 + change)
        h = max(o, c) * (1 + random.random() * 0.015)
        low = min(o, c) * (1 - random.random() * 0.015)
        price = c
        out.append({
            "date": f"2026-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}",
            "open": o, "high": h, "low": low, "close": c,
            "volume": random.randint(200_000, 3_000_000),
        })
    return out


# mock에 history 주입 (모듈 로드 시 한 번)
for _s in _MOCK_STOCKS:
    _s["history"] = _generate_mock_history(_s["price"])


# --- 자동 스케줄러 (매일 18:30 KST = 09:30 UTC) -------------------------

def _run_daily_job() -> None:
    """매일 시세 업데이트 + 1년 이전 데이터 삭제."""
    try:
        print("[scheduler] 일일 업데이트 시작")
        from data_collector import cmd_daily, cmd_cleanup
        cmd_daily()
        cmd_cleanup(keep_days=365)
        print("[scheduler] 일일 업데이트 완료 ✓")
    except Exception as e:
        print(f"[scheduler] 오류: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        scheduler = BackgroundScheduler(timezone="UTC")
        # 매일 09:30 UTC = 18:30 KST (장 마감 후)
        scheduler.add_job(_run_daily_job, CronTrigger(hour=9, minute=30))
        scheduler.start()
        print("[scheduler] 일일 스케줄러 시작 (매일 18:30 KST)")
    except ImportError:
        print("[scheduler] apscheduler 미설치 — 스케줄러 비활성화")
    yield


# --- FastAPI 앱 ---------------------------------------------------------

app = FastAPI(title="StockNLP API", version="0.1.0", lifespan=lifespan)

# 프로덕션: CORS_ORIGINS 환경변수에 Netlify URL 추가 (콤마 구분)
# 예) CORS_ORIGINS=https://stocknlp.netlify.app,https://your-domain.com
_CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)


def _load_stocks_from_db() -> list[dict[str, Any]] | None:
    sb = _supabase_or_none()
    if sb is None:
        return None
    try:
        rows = (
            sb.table("stocks")
            .select(
                "code, name, sector, is_leader, leader_name, buy_score, "
                "rsi, rsi_prev, profit_growth_years, close_price, change_pct, "
                "market_cap_trillion, dividend_yield, financials"
            )
            .order("buy_score", desc=True)
            .limit(100)
            .execute()
            .data
            or []
        )
        stocks: list[dict[str, Any]] = []
        for r in rows:
            # financials JSONB: DB에서 None 또는 불완전한 경우 안전하게 처리
            raw_fin = r.get("financials") or {}
            financials = {
                "revenue": raw_fin.get("revenue") or "-",
                "profit":  raw_fin.get("profit")  or "-",
                "roe":     raw_fin.get("roe")      or "-",
                "desc":    raw_fin.get("desc")     or "",
            }
            mkt_cap = r.get("market_cap_trillion")
            div_yield = r.get("dividend_yield")
            stocks.append({
                "code": r["code"],
                "name": r["name"],
                "sector": r.get("sector") or "기타",
                "is_leader": bool(r.get("is_leader")),
                "leader_name": r.get("leader_name") or r["name"],
                "buy_score": int(r.get("buy_score") or 0),
                "rsi": int(r.get("rsi") or 50),
                "rsi_prev": int(r.get("rsi_prev") or 50),
                "profit_growth_years": int(r.get("profit_growth_years") or 0),
                "price": int(r.get("close_price") or 0),
                "change": float(r.get("change_pct") or 0),
                "market_cap_trillion": round(float(mkt_cap), 2) if mkt_cap else None,
                "dividend_yield": round(float(div_yield), 2) if div_yield else None,
                "history": [],  # lazy-loaded via /history 엔드포인트
                "financials": financials,
            })
        return stocks if stocks else None
    except Exception as e:  # noqa: BLE001
        print(f"[stocks] DB load failed, falling back to mock: {e}")
        return None


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "supabase": bool(SUPABASE_URL and SUPABASE_ANON_KEY),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "now": datetime.utcnow().isoformat(),
    }


@app.get("/api/stocks")
def list_stocks() -> dict[str, Any]:
    stocks = _load_stocks_from_db()
    source = "api"
    if stocks is None:
        stocks = _MOCK_STOCKS
        source = "mock"
    return {
        "stocks": stocks,
        "source": source,
        "as_of": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        + (" · Supabase" if source == "api" else " · MOCK"),
    }


@app.get("/api/stocks/{code}/history")
def stock_history(code: str) -> dict[str, Any]:
    sb = _supabase_or_none()
    if sb is not None:
        try:
            rows = (
                sb.table("stock_prices")
                .select("date, open, high, low, close, volume")
                .eq("code", code)
                .order("date", desc=False)
                .limit(300)
                .execute()
                .data
                or []
            )
            if rows:
                return {"code": code, "history": rows}
        except Exception as e:  # noqa: BLE001
            print(f"[history] DB load failed: {e}")

    # 폴백
    for s in _MOCK_STOCKS:
        if s["code"] == code:
            return {"code": code, "history": s["history"]}
    raise HTTPException(404, f"no history for {code}")


class QueryBody(BaseModel):
    query: str


@app.post("/api/parse-query")
def parse_query(body: QueryBody) -> dict[str, Any]:
    if not body.query.strip():
        raise HTTPException(400, "query is empty")
    return gemini_parse(body.query)


def _apply_filters(stocks: list[dict[str, Any]], f: dict[str, Any]) -> list[dict[str, Any]]:
    def ok(s: dict[str, Any]) -> bool:
        rsi = f.get("rsi") or {}
        if rsi.get("min") is not None and s["rsi"] < rsi["min"]:
            return False
        if rsi.get("max") is not None and s["rsi"] > rsi["max"]:
            return False
        if f.get("profit_growth_years") is not None and s["profit_growth_years"] < f["profit_growth_years"]:
            return False
        if f.get("is_leader") is True and not s["is_leader"]:
            return False
        if f.get("sector") and s["sector"] != f["sector"]:
            return False
        # 시가총액 필터
        if f.get("market_cap_trillion_min") is not None:
            cap = s.get("market_cap_trillion")
            if cap is None or cap < f["market_cap_trillion_min"]:
                return False
        # 배당수익률 필터
        if f.get("dividend_yield_min") is not None:
            div = s.get("dividend_yield")
            if div is None or div < f["dividend_yield_min"]:
                return False
        return True

    return [s for s in stocks if ok(s)]


@app.get("/api/indices")
def list_indices() -> dict[str, Any]:
    """KOSPI / KOSDAQ / KRX300 최신 지수값."""
    sb = _supabase_or_none()
    if sb is not None:
        try:
            # 각 지수의 최근 5일 데이터 조회
            rows = (
                sb.table("market_indices")
                .select("idx_code, idx_name, date, close, change_pct")
                .order("date", desc=True)
                .limit(15)  # 3개 지수 × 최근 5일
                .execute()
                .data or []
            )
            if rows:
                # 지수별 최신값만 추출
                latest: dict[str, Any] = {}
                for r in rows:
                    code = r["idx_code"]
                    if code not in latest:
                        latest[code] = r
                return {"indices": list(latest.values()), "source": "api"}
        except Exception as e:
            print(f"[indices] DB load failed: {e}")

    # Mock 폴백
    return {
        "indices": [
            {"idx_code": "KOSPI",  "idx_name": "코스피",  "date": "2026-04-19", "close": 2650.3,  "change_pct": 0.52},
            {"idx_code": "KOSDAQ", "idx_name": "코스닥",  "date": "2026-04-19", "close": 860.7,   "change_pct": -0.21},
            {"idx_code": "KRX300", "idx_name": "KRX300", "date": "2026-04-19", "close": 1820.1,  "change_pct": 0.38},
        ],
        "source": "mock",
    }


@app.get("/api/commodities")
def list_commodities() -> dict[str, Any]:
    """금 / 원유 / 구리 최신 시세."""
    sb = _supabase_or_none()
    if sb is not None:
        try:
            rows = (
                sb.table("commodities")
                .select("code, name, date, close, unit")
                .order("date", desc=True)
                .limit(12)
                .execute()
                .data or []
            )
            if rows:
                latest: dict[str, Any] = {}
                for r in rows:
                    if r["code"] not in latest:
                        latest[r["code"]] = r
                return {"commodities": list(latest.values()), "source": "api"}
        except Exception as e:
            print(f"[commodities] DB load failed: {e}")

    return {
        "commodities": [
            {"code": "GOLD",      "name": "금",     "date": "2026-04-19", "close": 480250.0, "unit": "원/g"},
            {"code": "DUBAI_OIL", "name": "두바이유","date": "2026-04-19", "close": 74.3,    "unit": "달러/배럴"},
            {"code": "WTI",       "name": "WTI",    "date": "2026-04-19", "close": 72.1,    "unit": "달러/배럴"},
        ],
        "source": "mock",
    }


def _format_stock_row(r: dict[str, Any]) -> dict[str, Any]:
    raw_fin = r.get("financials") or {}
    financials = {
        "revenue": raw_fin.get("revenue") or "-",
        "profit":  raw_fin.get("profit")  or "-",
        "roe":     raw_fin.get("roe")      or "-",
        "desc":    raw_fin.get("desc")     or "",
    }
    mkt_cap   = r.get("market_cap_trillion")
    div_yield = r.get("dividend_yield")
    return {
        "code":                r["code"],
        "name":                r["name"],
        "sector":              r.get("sector") or "기타",
        "is_leader":           bool(r.get("is_leader")),
        "leader_name":         r.get("leader_name") or r["name"],
        "buy_score":           int(r.get("buy_score") or 0),
        "rsi":                 int(r.get("rsi") or 50),
        "rsi_prev":            int(r.get("rsi_prev") or 50),
        "profit_growth_years": int(r.get("profit_growth_years") or 0),
        "price":               int(r.get("close_price") or 0),
        "change":              float(r.get("change_pct") or 0),
        "market_cap_trillion": round(float(mkt_cap), 2) if mkt_cap else None,
        "dividend_yield":      round(float(div_yield), 2) if div_yield else None,
        "history":             [],
        "financials":          financials,
    }


def _search_by_date_change(
    target_date: str,
    change_min: float | None,
    change_max: float | None,
    extra_filters: dict[str, Any],
) -> list[dict[str, Any]] | None:
    """특정 날짜의 등락률 기준 종목 검색. stock_prices에서 전일대비 변화율 계산."""
    sb = _supabase_or_none()
    if sb is None:
        return None
    try:
        # 직전 거래일 찾기
        prev_rows = (
            sb.table("stock_prices").select("date")
            .lt("date", target_date).order("date", desc=True).limit(1)
            .execute().data or []
        )
        if not prev_rows:
            return []
        prev_date = prev_rows[0]["date"]

        # 대상 날짜 + 직전 거래일 종가 가져오기
        today_prices = (
            sb.table("stock_prices").select("code, close")
            .eq("date", target_date).limit(5000).execute().data or []
        )
        if not today_prices:
            return []  # 해당 날짜 데이터 없음 (휴장일 등)

        prev_prices = (
            sb.table("stock_prices").select("code, close")
            .eq("date", prev_date).limit(5000).execute().data or []
        )
        prev_close_map = {r["code"]: float(r["close"]) for r in prev_prices if r.get("close")}

        # 등락률 계산 후 필터링
        matching_codes = []
        for r in today_prices:
            code  = r["code"]
            close = float(r.get("close") or 0)
            pc    = prev_close_map.get(code)
            if not pc or pc <= 0:
                continue
            change = (close - pc) / pc * 100
            if change_min is not None and change < change_min:
                continue
            if change_max is not None and change > change_max:
                continue
            matching_codes.append(code)

        if not matching_codes:
            return []

        # 매칭 종목 상세 정보 조회
        results = []
        for i in range(0, len(matching_codes), 100):
            batch = matching_codes[i:i + 100]
            q = (
                sb.table("stocks")
                .select("code, name, sector, is_leader, leader_name, buy_score, "
                        "rsi, rsi_prev, profit_growth_years, close_price, change_pct, "
                        "market_cap_trillion, dividend_yield, financials")
                .in_("code", batch)
            )
            if extra_filters.get("sector"):
                q = q.eq("sector", extra_filters["sector"])
            if extra_filters.get("is_leader") is True:
                q = q.eq("is_leader", True)
            rows = q.execute().data or []
            results.extend(_format_stock_row(r) for r in rows)

        results.sort(key=lambda s: s["buy_score"], reverse=True)
        return results
    except Exception as e:
        print(f"[date_change_search] failed: {e}")
        return None


def _search_stocks_from_db(f: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Supabase 쿼리 레벨에서 필터 적용 → 전체 2,891개 종목 대상 검색."""
    sb = _supabase_or_none()
    if sb is None:
        return None
    try:
        q = sb.table("stocks").select(
            "code, name, sector, is_leader, leader_name, buy_score, "
            "rsi, rsi_prev, profit_growth_years, close_price, change_pct, "
            "market_cap_trillion, dividend_yield, financials"
        )
        # 섹터 필터
        if f.get("sector"):
            q = q.eq("sector", f["sector"])
        # RSI 범위
        rsi = f.get("rsi") or {}
        if rsi.get("min") is not None:
            q = q.gte("rsi", rsi["min"])
        if rsi.get("max") is not None:
            q = q.lte("rsi", rsi["max"])
        # 주도주 여부
        if f.get("is_leader") is True:
            q = q.eq("is_leader", True)
        # 연속 성장 연수
        if f.get("profit_growth_years") is not None:
            q = q.gte("profit_growth_years", f["profit_growth_years"])
        # 시가총액 최솟값
        if f.get("market_cap_trillion_min") is not None:
            q = q.gte("market_cap_trillion", f["market_cap_trillion_min"])
        # 배당수익률 최솟값
        if f.get("dividend_yield_min") is not None:
            q = q.gte("dividend_yield", f["dividend_yield_min"])
        # 당일 등락률 (날짜 미지정 시 stocks.change_pct 기준)
        if f.get("change_pct_min") is not None:
            q = q.gte("change_pct", f["change_pct_min"])
        if f.get("change_pct_max") is not None:
            q = q.lte("change_pct", f["change_pct_max"])

        rows = q.order("buy_score", desc=True).limit(200).execute().data or []
        print(f"[search] filters={f} → {len(rows)}개 결과")
        return [_format_stock_row(r) for r in rows]
    except Exception as e:
        print(f"[search] DB search failed: {e}")
        return None


@app.post("/api/search")
def search(body: QueryBody) -> dict[str, Any]:
    filters = gemini_parse(body.query)
    print(f"[search] query='{body.query}' → filters={filters}")

    target_date  = filters.get("target_date")
    change_min   = filters.get("change_pct_min")
    change_max   = filters.get("change_pct_max")

    # 날짜 지정 시 stock_prices 기반 등락률 검색
    if target_date and (change_min is not None or change_max is not None):
        results = _search_by_date_change(target_date, change_min, change_max, filters)
        if results is None:
            results = []
        note = f"{target_date} 기준 등락률 검색"
    else:
        results = _search_stocks_from_db(filters)
        if results is None:
            results = _apply_filters(_MOCK_STOCKS, filters)
            results.sort(key=lambda s: s["buy_score"], reverse=True)
        note = None

    resp: dict[str, Any] = {"filters": filters, "results": results, "count": len(results)}
    if note:
        resp["note"] = note
    return resp
