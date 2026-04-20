"""공공데이터포털 5개 API → Supabase 데이터 수집 파이프라인.

사용 API (모두 동일한 PUBLIC_DATA_KEY 사용):
  1. 금융위원회_주식시세정보    → OHLCV + 시가총액 + 상장주식수
  2. 금융위원회_지수시세정보    → KOSPI/KOSDAQ/KRX300 지수 추이
  3. 금융위원회_주식발행정보    → 상장주식수 (정밀 시총 보완)
  4. 금융위원회_주식배당정보    → 배당수익률
  5. 금융위원회_일반상품시세정보 → 금/원유/구리 등 원자재 시세

실행 예시:
    python data_collector.py --seed          # 최초 1회 전체 적재
    python data_collector.py --daily         # 매일 최신 업데이트 (cron)
    python data_collector.py --reindex       # RSI/buy_score 재계산만
    python data_collector.py --dart          # DART 재무 갱신 (선택)

.env 필수: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, PUBLIC_DATA_KEY
.env 선택: DART_API_KEY, GEMINI_API_KEY
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

from indicators import buy_score as calc_buy_score
from indicators import rsi as calc_rsi

load_dotenv()

SUPABASE_URL    = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY    = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
PUBLIC_DATA_KEY = os.getenv("PUBLIC_DATA_KEY", "")
DART_API_KEY    = os.getenv("DART_API_KEY", "")

# ── 공공데이터포털 API 베이스 URL ─────────────────────────────────────────
_BASE = "http://apis.data.go.kr/1160100/service"

APIS = {
    "price":     f"{_BASE}/GetStockSecuritiesInfoService/getStockPriceInfo",
    "index":     f"{_BASE}/GetMarketIndexInfoService/getMarketIndexInfo",
    "issuance":  f"{_BASE}/GetStockIssuanceInfoService/getStockIssuanceInfo",
    "dividend":  f"{_BASE}/GetStockDividendInfoService/getStockDividendInfo",
    "commodity": f"{_BASE}/GetGeneralCommodityPriceInfoService/getGeneralCommodityPriceInfo",
}

# 지수 수집 대상
INDEX_NAMES = {
    "코스피":  "KOSPI",
    "코스닥":  "KOSDAQ",
    "KRX300": "KRX300",
}

# 상품 수집 대상 (API에서 반환되는 itmsNm 기준으로 필터링)
COMMODITY_TARGETS = {
    "금": {"code": "GOLD", "unit": "원/g"},
    "두바이유": {"code": "DUBAI_OIL", "unit": "달러/배럴"},
    "WTI": {"code": "WTI", "unit": "달러/배럴"},
    "구리": {"code": "COPPER", "unit": "달러/톤"},
}

# ── 섹터 + 주도주 curated 매핑 ────────────────────────────────────────────
STOCK_META: dict[str, dict[str, Any]] = {
    # 반도체
    "000660": {"name": "SK하이닉스",       "sector": "반도체",  "leader": "000660"},
    "005930": {"name": "삼성전자",         "sector": "반도체",  "leader": "000660"},
    "009150": {"name": "삼성전기",         "sector": "반도체",  "leader": "000660"},
    "042700": {"name": "한미반도체",       "sector": "반도체",  "leader": "000660"},
    "058470": {"name": "리노공업",         "sector": "반도체",  "leader": "000660"},
    # 자동차
    "005380": {"name": "현대차",           "sector": "자동차",  "leader": "005380"},
    "000270": {"name": "기아",             "sector": "자동차",  "leader": "005380"},
    "012330": {"name": "현대모비스",       "sector": "자동차",  "leader": "005380"},
    "011210": {"name": "현대위아",         "sector": "자동차",  "leader": "005380"},
    # 2차전지
    "373220": {"name": "LG에너지솔루션",   "sector": "2차전지", "leader": "373220"},
    "006400": {"name": "삼성SDI",          "sector": "2차전지", "leader": "373220"},
    "051910": {"name": "LG화학",           "sector": "2차전지", "leader": "373220"},
    "247540": {"name": "에코프로비엠",     "sector": "2차전지", "leader": "373220"},
    "086520": {"name": "에코프로",         "sector": "2차전지", "leader": "373220"},
    # 인터넷
    "035420": {"name": "NAVER",            "sector": "인터넷",  "leader": "035420"},
    "035720": {"name": "카카오",           "sector": "인터넷",  "leader": "035420"},
    "259960": {"name": "크래프톤",         "sector": "인터넷",  "leader": "035420"},
    # 바이오
    "207940": {"name": "삼성바이오로직스", "sector": "바이오",  "leader": "207940"},
    "068270": {"name": "셀트리온",         "sector": "바이오",  "leader": "207940"},
    "000100": {"name": "유한양행",         "sector": "바이오",  "leader": "207940"},
    "128940": {"name": "한미약품",         "sector": "바이오",  "leader": "207940"},
    # 금융
    "105560": {"name": "KB금융",           "sector": "금융",    "leader": "105560"},
    "055550": {"name": "신한지주",         "sector": "금융",    "leader": "105560"},
    "086790": {"name": "하나금융지주",     "sector": "금융",    "leader": "105560"},
    "316140": {"name": "우리금융지주",     "sector": "금융",    "leader": "105560"},
    "032830": {"name": "삼성생명",         "sector": "금융",    "leader": "105560"},
    # 철강
    "005490": {"name": "POSCO홀딩스",      "sector": "철강",    "leader": "005490"},
    "004020": {"name": "현대제철",         "sector": "철강",    "leader": "005490"},
    # 화학
    "009830": {"name": "한화솔루션",       "sector": "화학",    "leader": "051910"},
    "011170": {"name": "롯데케미칼",       "sector": "화학",    "leader": "051910"},
    # 통신
    "017670": {"name": "SK텔레콤",         "sector": "통신",    "leader": "017670"},
    "030200": {"name": "KT",               "sector": "통신",    "leader": "017670"},
    "032640": {"name": "LG유플러스",       "sector": "통신",    "leader": "017670"},
    # 건설
    "000720": {"name": "현대건설",         "sector": "건설",    "leader": "000720"},
    "006360": {"name": "GS건설",           "sector": "건설",    "leader": "000720"},
    # 유통
    "139480": {"name": "이마트",           "sector": "유통",    "leader": "139480"},
    "023530": {"name": "롯데쇼핑",         "sector": "유통",    "leader": "139480"},
    # 엔터
    "352820": {"name": "HYBE",             "sector": "엔터",    "leader": "352820"},
    "041510": {"name": "SM엔터테인먼트",   "sector": "엔터",    "leader": "352820"},
    "035900": {"name": "JYP엔터테인먼트",  "sector": "엔터",    "leader": "352820"},
    # 게임
    "036570": {"name": "엔씨소프트",       "sector": "게임",    "leader": "036570"},
    "251270": {"name": "넷마블",           "sector": "게임",    "leader": "036570"},
    "293490": {"name": "카카오게임즈",     "sector": "게임",    "leader": "036570"},
}


# ── 공통 유틸 ─────────────────────────────────────────────────────────────

def _require_env(for_dart: bool = False) -> None:
    missing = [k for k, v in {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_KEY,
        "PUBLIC_DATA_KEY": PUBLIC_DATA_KEY,
    }.items() if not v]
    if for_dart and not DART_API_KEY:
        missing.append("DART_API_KEY")
    if missing:
        raise RuntimeError(
            f".env에 다음 값이 필요합니다: {', '.join(missing)}\n"
            "→ backend/.env.example 참고"
        )


def _supabase():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _fmt(d: date) -> str:
    return d.strftime("%Y%m%d")


def _today() -> str:
    return _fmt(date.today())


def _ago(n: int) -> str:
    return _fmt(date.today() - timedelta(days=n))


def _iso(s: str) -> str:
    """'20260101' → '2026-01-01'."""
    s = str(s)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 else s


def _api_get(url: str, extra_params: dict) -> list[dict]:
    """공통 API 호출. items 리스트 반환, 실패 시 []."""
    params = {
        "serviceKey": PUBLIC_DATA_KEY,
        "resultType": "json",
        "numOfRows": "1000",
        "pageNo": "1",
        **extra_params,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        body = r.json().get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        return [items] if isinstance(items, dict) else (items or [])
    except Exception as e:
        print(f"  [API ERROR] {url.split('/')[-1]}: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════
# 1. 주식시세정보 — OHLCV + 시가총액 + 상장주식수
# ══════════════════════════════════════════════════════════════════════════

def fetch_price_range(code: str, begin: str, end: str) -> list[dict]:
    """단일 종목의 날짜 범위 OHLCV + 시총 조회."""
    items = _api_get(APIS["price"], {
        "srtnCd": code,
        "beginBasDt": begin,
        "endBasDt": end,
        "numOfRows": "200",
    })
    rows = []
    for it in items:
        try:
            rows.append({
                "date":            _iso(it.get("basDt", "")),
                "open":            float(it.get("mkp",  0) or 0),
                "high":            float(it.get("hipr", 0) or 0),
                "low":             float(it.get("lopr", 0) or 0),
                "close":           float(it.get("clpr", 0) or 0),
                "volume":          int(float(it.get("trqu", 0) or 0)),
                # 시세정보에서 바로 가져올 수 있는 추가 필드
                "_fltRt":          float(it.get("fltRt", 0) or 0),
                "_mrktTotAmt":     float(it.get("mrktTotAmt", 0) or 0),   # 시가총액 (원)
                "_lstgStCnt":      int(float(it.get("lstgStCnt", 0) or 0)), # 상장주식수
            })
        except (ValueError, TypeError):
            continue
    rows.sort(key=lambda x: x["date"])
    return rows


# ══════════════════════════════════════════════════════════════════════════
# 2. 지수시세정보 — KOSPI / KOSDAQ / KRX300
# ══════════════════════════════════════════════════════════════════════════

def fetch_index_range(begin: str, end: str) -> list[dict]:
    """KOSPI/KOSDAQ/KRX300 지수 시세 조회."""
    items = _api_get(APIS["index"], {
        "beginBasDt": begin,
        "endBasDt": end,
        "numOfRows": "1000",
    })
    rows = []
    for it in items:
        name = str(it.get("idxNm", "")).strip()
        code = INDEX_NAMES.get(name)
        if not code:
            continue  # 대상 지수만 저장
        try:
            rows.append({
                "idx_code":   code,
                "idx_name":   name,
                "date":       _iso(it.get("basDt", "")),
                "close":      float(it.get("clpr", 0) or 0),
                "change_pct": float(it.get("fltRt", 0) or 0),
            })
        except (ValueError, TypeError):
            continue
    return rows


# ══════════════════════════════════════════════════════════════════════════
# 3. 주식발행정보 — 상장주식수 (시총 정밀 계산 보완)
# ══════════════════════════════════════════════════════════════════════════

def fetch_issuance_all(base_date: str | None = None) -> dict[str, int]:
    """전 종목 상장주식수 조회. {code: listed_shares} 반환."""
    params: dict[str, Any] = {"numOfRows": "200"}
    if base_date:
        params["basDt"] = base_date
    items = _api_get(APIS["issuance"], params)
    result: dict[str, int] = {}
    for it in items:
        code = str(it.get("srtnCd", "")).strip()
        cnt  = it.get("lstgStCnt") or it.get("stckIssuCnt")
        if code and cnt:
            try:
                result[code] = int(float(str(cnt).replace(",", "")))
            except (ValueError, TypeError):
                pass
    return result


# ══════════════════════════════════════════════════════════════════════════
# 4. 주식배당정보 — 배당수익률 / 주당 배당금
# ══════════════════════════════════════════════════════════════════════════

def fetch_dividends_all(year: int | None = None) -> dict[str, dict]:
    """전 종목 배당 정보 조회. {code: {yield, amount}} 반환."""
    y = year or (date.today().year - 1)
    # 배당기준일 범위: 해당 연도 전체
    params = {
        "beginBasDt": f"{y}0101",
        "endBasDt":   f"{y}1231",
        "numOfRows":  "500",
    }
    items = _api_get(APIS["dividend"], params)
    result: dict[str, dict] = {}
    for it in items:
        code = str(it.get("srtnCd", "")).strip()
        if not code:
            continue
        try:
            # dividendYd: 배당수익률(%) / dvdnAmt: 주당배당금(원)
            div_yield  = float(it.get("dividendYd", 0) or 0)
            div_amount = float(it.get("dvdnAmt", 0) or 0)
            if code not in result or div_yield > result[code].get("yield", 0):
                result[code] = {"yield": div_yield, "amount": div_amount}
        except (ValueError, TypeError):
            continue
    return result


# ══════════════════════════════════════════════════════════════════════════
# 5. 일반상품시세정보 — 금 / 원유 / 구리
# ══════════════════════════════════════════════════════════════════════════

def fetch_commodity_range(begin: str, end: str) -> list[dict]:
    """금/원유/구리 시세 조회."""
    items = _api_get(APIS["commodity"], {
        "beginBasDt": begin,
        "endBasDt": end,
        "numOfRows": "1000",
    })
    rows = []
    for it in items:
        name = str(it.get("itmsNm", "") or it.get("cmdtClNm", "")).strip()
        target = COMMODITY_TARGETS.get(name)
        if not target:
            continue
        try:
            rows.append({
                "code":  target["code"],
                "name":  name,
                "date":  _iso(it.get("basDt", "")),
                "close": float(it.get("clpr", 0) or 0),
                "unit":  target["unit"],
            })
        except (ValueError, TypeError):
            continue
    return rows


# ── 지표 계산 ─────────────────────────────────────────────────────────────

def _calc_indicators(rows: list[dict], is_leader: bool) -> dict[str, Any]:
    if len(rows) < 5:
        return {"rsi": 50, "rsi_prev": 50, "buy_score": 40, "profit_growth_years": 0}
    close    = pd.Series([r["close"] for r in rows], dtype=float)
    rsi_s    = calc_rsi(close)
    rsi_now  = float(rsi_s.iloc[-1])
    rsi_prev = float(rsi_s.iloc[-2]) if len(rsi_s) > 1 else rsi_now
    ma60     = close.rolling(60, min_periods=1).mean().iloc[-1]
    pvm60    = (close.iloc[-1] - ma60) / ma60 if ma60 else 0.0
    score    = calc_buy_score(rsi_now, rsi_prev, 0, is_leader, float(pvm60))
    return {"rsi": int(round(rsi_now)), "rsi_prev": int(round(rsi_prev)),
            "buy_score": score, "profit_growth_years": 0}


# ── DART 재무 ─────────────────────────────────────────────────────────────

_DART_CORP_MAP: dict[str, str] | None = None


def _get_corp_code(stock_code: str) -> str | None:
    global _DART_CORP_MAP
    if _DART_CORP_MAP is None:
        try:
            import io, zipfile, xml.etree.ElementTree as ET
            r = requests.get("https://opendart.fss.or.kr/api/corpCode.xml",
                             params={"crtfc_key": DART_API_KEY}, timeout=30)
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                with z.open("CORPCODE.xml") as f:
                    tree = ET.parse(f)
            _DART_CORP_MAP = {}
            for el in tree.getroot().findall("list"):
                sc = (el.findtext("stock_code") or "").strip()
                cc = (el.findtext("corp_code") or "").strip()
                if sc:
                    _DART_CORP_MAP[sc] = cc
        except Exception as e:
            print(f"  [DART] corp_code 다운로드 실패: {e}")
            _DART_CORP_MAP = {}
    return _DART_CORP_MAP.get(stock_code)


def _dart_financials(corp_code: str) -> dict | None:
    try:
        r = requests.get("https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
                         params={"crtfc_key": DART_API_KEY, "corp_code": corp_code,
                                 "bsns_year": str(date.today().year - 1),
                                 "reprt_code": "11011", "fs_div": "CFS"}, timeout=15)
        rev = prof = None
        for it in r.json().get("list", []):
            nm  = it.get("account_nm", "")
            val = it.get("thstrm_amount", "").replace(",", "").replace("-", "0")
            try:
                vf = float(val)
            except (ValueError, TypeError):
                continue
            if "매출액" in nm and rev is None:
                rev = vf
            elif "영업이익" in nm and prof is None:
                prof = vf
        if rev and prof and rev > 0:
            return {"revenue": f"{rev/1e12:.1f}조", "profit": f"{prof/1e12:.1f}조",
                    "roe": f"{round(prof/rev*100,1)}%", "desc": ""}
    except Exception as e:
        print(f"  [DART] 재무 조회 실패: {e}")
    return None


# ══════════════════════════════════════════════════════════════════════════
# 수집 모드
# ══════════════════════════════════════════════════════════════════════════

def cmd_seed(months: int = 6) -> None:
    """최초 1회: 5개 API 전체 적재."""
    sb    = _supabase()
    begin = _ago(months * 31)
    end   = _today()
    total = len(STOCK_META)

    print(f"\n{'='*60}")
    print(f"[seed] {total}개 종목 × {months}개월 전체 적재 시작")
    print(f"       기간: {begin} ~ {end}")
    print(f"{'='*60}\n")

    # ── 1단계: 발행정보 (상장주식수) 일괄 조회 ────────────────────────
    print("[1/5] 주식발행정보 (상장주식수) 조회 중...", end=" ", flush=True)
    issuance_map = fetch_issuance_all()
    print(f"✓ {len(issuance_map)}개 종목")
    time.sleep(0.5)

    # ── 2단계: 배당정보 일괄 조회 ────────────────────────────────────
    print("[2/5] 주식배당정보 (배당수익률) 조회 중...", end=" ", flush=True)
    dividend_map = fetch_dividends_all()
    print(f"✓ {len(dividend_map)}개 종목")
    time.sleep(0.5)

    # ── 3단계: 지수시세 조회 ─────────────────────────────────────────
    print("[3/5] 지수시세정보 (KOSPI/KOSDAQ/KRX300) 조회 중...", end=" ", flush=True)
    idx_rows = fetch_index_range(begin, end)
    if idx_rows:
        sb.table("market_indices").upsert(idx_rows, on_conflict="idx_code,date").execute()
    print(f"✓ {len(idx_rows)}행")
    time.sleep(0.5)

    # ── 4단계: 원자재 시세 조회 ──────────────────────────────────────
    print("[4/5] 일반상품시세정보 (금/원유/구리) 조회 중...", end=" ", flush=True)
    cmd_rows = fetch_commodity_range(begin, end)
    if cmd_rows:
        sb.table("commodities").upsert(cmd_rows, on_conflict="code,date").execute()
    print(f"✓ {len(cmd_rows)}행")
    time.sleep(0.5)

    # ── 5단계: 종목별 시세 + 적재 ────────────────────────────────────
    print(f"\n[5/5] 주식시세정보 종목별 OHLCV 적재 ({total}개):\n")

    for i, (code, meta) in enumerate(STOCK_META.items(), 1):
        is_leader  = (meta["leader"] == code)
        leader_meta = STOCK_META.get(meta["leader"], meta)
        name       = meta["name"]

        print(f"  [{i:02d}/{total}] {name}({code}) ...", end=" ", flush=True)
        rows = fetch_price_range(code, begin, end)

        if not rows:
            print("⚠ 데이터 없음")
            time.sleep(1.0)
            continue

        # 시총 계산: API의 mrktTotAmt 우선, 없으면 close × listed_shares
        last          = rows[-1]
        close_price   = int(last["close"])
        change_pct    = round(last["_fltRt"], 2)
        mkt_won       = last.get("_mrktTotAmt") or 0  # 원 단위
        listed_shares = last.get("_lstgStCnt") or issuance_map.get(code, 0)

        if mkt_won == 0 and listed_shares and close_price:
            mkt_won = close_price * listed_shares  # 추정 시총

        market_cap_trillion = round(mkt_won / 1e12, 2) if mkt_won else None

        # 배당수익률
        div_info      = dividend_map.get(code, {})
        dividend_yield = round(div_info.get("yield", 0), 2) or None

        # 기술적 지표
        indic = _calc_indicators(rows, is_leader)

        # stocks upsert
        sb.table("stocks").upsert({
            "code":                code,
            "name":                name,
            "sector":              meta["sector"],
            "is_leader":           is_leader,
            "leader_name":         leader_meta["name"],
            "close_price":         close_price,
            "change_pct":          change_pct,
            "market_cap_trillion": market_cap_trillion,
            "dividend_yield":      dividend_yield,
            "listed_shares":       listed_shares or None,
            "financials":          {"revenue": "-", "profit": "-", "roe": "-", "desc": ""},
            "updated_at":          datetime.utcnow().isoformat(),
            **indic,
        }, on_conflict="code").execute()

        # stock_prices bulk upsert
        price_rows = [{"code": code, "date": r["date"], "open": r["open"],
                       "high": r["high"], "low": r["low"], "close": r["close"],
                       "volume": r["volume"]} for r in rows if r["date"]]
        for j in range(0, len(price_rows), 200):
            sb.table("stock_prices").upsert(
                price_rows[j:j+200], on_conflict="code,date"
            ).execute()

        cap_str = f"{market_cap_trillion:.1f}조" if market_cap_trillion else "-"
        div_str = f"{dividend_yield:.1f}%" if dividend_yield else "-"
        print(f"✓ {len(rows)}일 | RSI={indic['rsi']} | 시총={cap_str} | 배당={div_str}")
        time.sleep(1.2)

    print(f"\n{'='*60}")
    print("[seed] 전체 완료 ✓")
    print(f"{'='*60}\n")


def cmd_daily() -> None:
    """매일 cron: 시세 + 지수 + 원자재 최신 업데이트."""
    sb    = _supabase()
    begin = _ago(20)
    end   = _today()
    total = len(STOCK_META)
    print(f"[daily] {total}개 종목 + 지수 + 원자재 일일 업데이트 ({end})")

    # 지수 업데이트
    print("  지수시세 ...", end=" ", flush=True)
    idx_rows = fetch_index_range(_ago(5), end)
    if idx_rows:
        sb.table("market_indices").upsert(idx_rows, on_conflict="idx_code,date").execute()
    print(f"✓ {len(idx_rows)}행")

    # 원자재 업데이트
    print("  원자재 ...", end=" ", flush=True)
    cmd_rows = fetch_commodity_range(_ago(5), end)
    if cmd_rows:
        sb.table("commodities").upsert(cmd_rows, on_conflict="code,date").execute()
    print(f"✓ {len(cmd_rows)}행")

    # 배당정보 (연초 1회로 충분하지만 daily에도 포함)
    print("  배당정보 ...", end=" ", flush=True)
    dividend_map = fetch_dividends_all()
    print(f"✓ {len(dividend_map)}개")

    # 종목별 시세
    for i, (code, meta) in enumerate(STOCK_META.items(), 1):
        is_leader = (meta["leader"] == code)
        print(f"  [{i:02d}/{total}] {meta['name']}({code}) ...", end=" ", flush=True)
        rows = fetch_price_range(code, begin, end)
        if not rows:
            print("⚠ 스킵")
            time.sleep(0.5)
            continue

        price_rows = [{"code": code, "date": r["date"], "open": r["open"],
                       "high": r["high"], "low": r["low"], "close": r["close"],
                       "volume": r["volume"]} for r in rows if r["date"]]
        sb.table("stock_prices").upsert(price_rows, on_conflict="code,date").execute()

        hist = (sb.table("stock_prices").select("date,close").eq("code", code)
                .order("date", desc=False).limit(200).execute().data or [])
        calc_rows = [{"close": float(h["close"])} for h in hist] if hist else rows
        indic = _calc_indicators(calc_rows, is_leader)

        last        = rows[-1]
        close_price = int(last["close"])
        change_pct  = round(last["_fltRt"], 2)
        mkt_won     = last.get("_mrktTotAmt") or 0
        mkt_cap     = round(mkt_won / 1e12, 2) if mkt_won else None
        div_info    = dividend_map.get(code, {})
        div_yield   = round(div_info.get("yield", 0), 2) or None

        sb.table("stocks").update({
            "close_price": close_price, "change_pct": change_pct,
            "market_cap_trillion": mkt_cap, "dividend_yield": div_yield,
            "updated_at": datetime.utcnow().isoformat(), **indic,
        }).eq("code", code).execute()
        print(f"✓ RSI={indic['rsi']}, 시총={f'{mkt_cap:.1f}조' if mkt_cap else '-'}")
        time.sleep(1.0)

    print("[daily] 완료 ✓")


def cmd_reindex() -> None:
    """RSI/buy_score만 재계산."""
    sb     = _supabase()
    stocks = sb.table("stocks").select("code, is_leader").execute().data or []
    print(f"[reindex] {len(stocks)}개 종목 지표 재계산")
    updated = 0
    for s in stocks:
        code      = s["code"]
        is_leader = bool(s.get("is_leader"))
        hist = (sb.table("stock_prices").select("date,close").eq("code", code)
                .order("date", desc=False).limit(200).execute().data or [])
        if len(hist) < 5:
            continue
        indic = _calc_indicators([{"close": float(h["close"])} for h in hist], is_leader)
        sb.table("stocks").update({**indic, "updated_at": datetime.utcnow().isoformat()}).eq("code", code).execute()
        updated += 1
    print(f"[reindex] {updated}개 완료 ✓")


def cmd_dart() -> None:
    """DART API로 재무 데이터 갱신."""
    sb     = _supabase()
    stocks = sb.table("stocks").select("code, name").execute().data or []
    print(f"[dart] {len(stocks)}개 종목 재무 수집")
    print("  corp_code 매핑 다운로드...", end=" ", flush=True)
    _get_corp_code("000000")
    print("✓")
    for s in stocks:
        code = s["code"]
        name = s["name"]
        cc   = _get_corp_code(code)
        if not cc:
            print(f"  {name}({code}) ⚠ corp_code 없음")
            continue
        fin = _dart_financials(cc)
        if fin:
            sb.table("stocks").update({"financials": fin}).eq("code", code).execute()
            print(f"  {name}({code}) ✓ 매출={fin['revenue']}, 영업익={fin['profit']}")
        else:
            print(f"  {name}({code}) 재무 없음")
        time.sleep(0.5)
    print("[dart] 완료 ✓")


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="StockNLP 데이터 수집기 (공공데이터포털 5개 API)")
    parser.add_argument("--seed",    action="store_true", help="최초 1회 전체 적재")
    parser.add_argument("--daily",   action="store_true", help="매일 최신 업데이트 (cron)")
    parser.add_argument("--reindex", action="store_true", help="RSI/buy_score 재계산만")
    parser.add_argument("--dart",    action="store_true", help="DART 재무 갱신")
    parser.add_argument("--months",  type=int, default=6, help="시드 기간 (기본 6개월)")
    args = parser.parse_args()

    _require_env(for_dart=args.dart)

    if   args.seed:    cmd_seed(months=args.months)
    elif args.daily:   cmd_daily()
    elif args.reindex: cmd_reindex()
    elif args.dart:    cmd_dart()
    else:
        parser.print_help()
        print("\n예시: python data_collector.py --seed")


if __name__ == "__main__":
    main()
