"""공공데이터포털 주식시세 API → Supabase 전체 상장 종목 수집 파이프라인.

변경 사항 (전체 종목 버전):
  - 종목별 개별 API 호출 → 날짜별 전체 종목 일괄 조회로 전환
  - 하드코딩 43개 → 공공데이터포털에서 전체 상장 종목 자동 수집

실행 예시:
    python data_collector.py --seed            # 최초 1회 전체 적재 (약 30분)
    python data_collector.py --daily           # 매일 최신 업데이트
    python data_collector.py --reindex         # RSI/buy_score 재계산만
    python data_collector.py --update-sectors  # Gemini로 전체 종목 섹터 자동 분류 (~10분)
    python data_collector.py --dart            # DART 재무 갱신 (선택)
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import date, datetime, timedelta, timezone
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

_BASE = "http://apis.data.go.kr/1160100/service"
PRICE_API = f"{_BASE}/GetStockSecuritiesInfoService/getStockPriceInfo"

# 전체 섹터 목록 (기타 최소화)
SECTOR_LIST = [
    "반도체", "자동차", "2차전지", "인터넷", "바이오", "금융",
    "화학", "철강", "통신", "건설", "유통", "엔터", "게임",
    "방산", "조선", "기계장비", "에너지", "음식료", "의료기기",
    "소프트웨어", "의류패션", "운송물류", "부동산", "기타",
]

# ── 섹터 + 주도주 curated 매핑 (알려진 종목만, 나머지는 "기타") ──────────────
STOCK_META: dict[str, dict[str, Any]] = {
    # 반도체 — 리더: SK하이닉스
    "000660": {"sector": "반도체",  "leader": "000660"},  # SK하이닉스
    "005930": {"sector": "반도체",  "leader": "000660"},  # 삼성전자
    "009150": {"sector": "반도체",  "leader": "000660"},  # 삼성전기
    "042700": {"sector": "반도체",  "leader": "000660"},  # 한미반도체
    "058470": {"sector": "반도체",  "leader": "000660"},  # 리노공업
    "034220": {"sector": "반도체",  "leader": "000660"},  # LG디스플레이
    "000990": {"sector": "반도체",  "leader": "000660"},  # DB하이텍
    # 자동차 — 리더: 현대차
    "005380": {"sector": "자동차",  "leader": "005380"},  # 현대차
    "000270": {"sector": "자동차",  "leader": "005380"},  # 기아
    "012330": {"sector": "자동차",  "leader": "005380"},  # 현대모비스
    "011210": {"sector": "자동차",  "leader": "005380"},  # 현대위아
    "007340": {"sector": "자동차",  "leader": "005380"},  # 현대건설기계
    # 2차전지 — 리더: LG에너지솔루션
    "373220": {"sector": "2차전지", "leader": "373220"},  # LG에너지솔루션
    "006400": {"sector": "2차전지", "leader": "373220"},  # 삼성SDI
    "051910": {"sector": "2차전지", "leader": "373220"},  # LG화학
    "247540": {"sector": "2차전지", "leader": "373220"},  # 에코프로비엠
    "086520": {"sector": "2차전지", "leader": "373220"},  # 에코프로
    "096770": {"sector": "2차전지", "leader": "373220"},  # SK이노베이션
    "011790": {"sector": "2차전지", "leader": "373220"},  # SKC
    # 인터넷/플랫폼 — 리더: NAVER
    "035420": {"sector": "인터넷",  "leader": "035420"},  # NAVER
    "035720": {"sector": "인터넷",  "leader": "035420"},  # 카카오
    "259960": {"sector": "인터넷",  "leader": "035420"},  # 크래프톤
    # 바이오 — 리더: 삼성바이오로직스
    "207940": {"sector": "바이오",  "leader": "207940"},  # 삼성바이오로직스
    "068270": {"sector": "바이오",  "leader": "207940"},  # 셀트리온
    "128940": {"sector": "바이오",  "leader": "207940"},  # 한미약품
    "009420": {"sector": "바이오",  "leader": "207940"},  # 한올바이오파마
    "000100": {"sector": "바이오",  "leader": "207940"},  # 유한양행
    # 금융 — 리더: KB금융
    "105560": {"sector": "금융",    "leader": "105560"},  # KB금융
    "055550": {"sector": "금융",    "leader": "105560"},  # 신한지주
    "086790": {"sector": "금융",    "leader": "105560"},  # 하나금융지주
    "316140": {"sector": "금융",    "leader": "105560"},  # 우리금융지주
    "032830": {"sector": "금융",    "leader": "105560"},  # 삼성생명
    "000810": {"sector": "금융",    "leader": "105560"},  # 삼성화재 (금융, 건설 아님)
    "003550": {"sector": "금융",    "leader": "105560"},  # LG
    "139130": {"sector": "금융",    "leader": "105560"},  # DGB금융지주
    # 화학 — 리더: LG화학
    "010950": {"sector": "화학",    "leader": "010950"},  # S-Oil
    "011170": {"sector": "화학",    "leader": "010950"},  # 롯데케미칼
    "006400": {"sector": "화학",    "leader": "010950"},  # 삼성SDI (중복 허용, 2차전지 우선)
    # 철강 — 리더: POSCO홀딩스
    "005490": {"sector": "철강",    "leader": "005490"},  # POSCO홀딩스
    "004020": {"sector": "철강",    "leader": "005490"},  # 현대제철
    "001230": {"sector": "철강",    "leader": "005490"},  # 동국제강
    # 통신 — 리더: KT
    "030200": {"sector": "통신",    "leader": "030200"},  # KT
    "017670": {"sector": "통신",    "leader": "030200"},  # SK텔레콤
    "032640": {"sector": "통신",    "leader": "030200"},  # LG유플러스
    # 건설 — 리더: 현대건설 (000810 삼성화재는 금융으로 이동)
    "000720": {"sector": "건설",    "leader": "000720"},  # 현대건설
    "006360": {"sector": "건설",    "leader": "000720"},  # GS건설
    "028260": {"sector": "건설",    "leader": "000720"},  # 삼성물산
    "028050": {"sector": "건설",    "leader": "000720"},  # 삼성E&A
    "047040": {"sector": "건설",    "leader": "000720"},  # 대우건설
    # 유통 — 리더: 이마트
    "139480": {"sector": "유통",    "leader": "139480"},  # 이마트
    "004170": {"sector": "유통",    "leader": "139480"},  # 신세계
    "023530": {"sector": "유통",    "leader": "139480"},  # 롯데쇼핑
    # 엔터 — 리더: HYBE
    "352820": {"sector": "엔터",    "leader": "352820"},  # HYBE
    "041510": {"sector": "엔터",    "leader": "352820"},  # SM엔터테인먼트
    "035900": {"sector": "엔터",    "leader": "352820"},  # JYP엔터테인먼트
    "122870": {"sector": "엔터",    "leader": "352820"},  # YG엔터테인먼트
    # 게임 — 리더: 크래프톤
    "263750": {"sector": "게임",    "leader": "263750"},  # 크래프톤
    "036570": {"sector": "게임",    "leader": "263750"},  # 엔씨소프트
    "251270": {"sector": "게임",    "leader": "263750"},  # 넷마블
    "225570": {"sector": "게임",    "leader": "263750"},  # 넥슨게임즈
    "112040": {"sector": "게임",    "leader": "263750"},  # 위메이드
    # 방산 — 리더: 한화에어로스페이스
    "012450": {"sector": "방산",    "leader": "012450"},  # 한화에어로스페이스
    "047810": {"sector": "방산",    "leader": "012450"},  # 한국항공우주
    "064350": {"sector": "방산",    "leader": "012450"},  # 현대로템
    "010140": {"sector": "방산",    "leader": "012450"},  # 삼성중공업
    # 조선 — 리더: HD현대중공업
    "329180": {"sector": "조선",    "leader": "329180"},  # HD현대중공업
    "042660": {"sector": "조선",    "leader": "329180"},  # 한화오션
    "009540": {"sector": "조선",    "leader": "329180"},  # HD한국조선해양
}


def _supabase():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _require_env(for_dart: bool = False) -> None:
    missing = [k for k in ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "PUBLIC_DATA_KEY"]
               if not os.getenv(k)]
    if for_dart and not DART_API_KEY:
        missing.append("DART_API_KEY")
    if missing:
        raise SystemExit(f"[ERROR] 필수 환경변수 없음: {', '.join(missing)}")


def _trading_dates(n_days: int = 35) -> list[str]:
    """최근 n_days개 영업일 날짜 리스트 (오래된 순)."""
    result = []
    d = date.today()
    while len(result) < n_days:
        if d.weekday() < 5:  # 월~금
            result.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    result.reverse()
    return result


def _calc_indicators(prices: list[dict], is_leader: bool) -> dict[str, Any]:
    closes = [float(p["close"]) for p in prices if p.get("close")]
    if len(closes) < 5:
        return {"rsi": 50, "rsi_prev": 50, "buy_score": 0, "profit_growth_years": 0}
    s = pd.Series(closes)
    rsi_series = calc_rsi(s)
    rsi_now  = int(rsi_series.iloc[-1])
    rsi_prev = int(calc_rsi(s.iloc[:-1]).iloc[-1]) if len(closes) > 1 else rsi_now
    # buy_score(rsi_value, rsi_prev, growth_years, is_leader, price_vs_ma60)
    ma60 = float(s.rolling(60, min_periods=1).mean().iloc[-1])
    price_vs_ma60 = (closes[-1] - ma60) / ma60 if ma60 else 0.0
    score = int(calc_buy_score(rsi_now, rsi_prev, 0, is_leader, price_vs_ma60))
    return {"rsi": rsi_now, "rsi_prev": rsi_prev, "buy_score": score, "profit_growth_years": 0}


# ── 날짜별 전체 종목 조회 ─────────────────────────────────────────────────────

def fetch_all_for_date(bas_dt: str) -> list[dict]:
    """특정 날짜의 전체 상장 종목 시세 (페이지네이션)."""
    all_items: list[dict] = []
    page = 1
    while True:
        params = {
            "serviceKey": PUBLIC_DATA_KEY,
            "resultType": "json",
            "numOfRows": 1000,
            "pageNo": page,
            "basDt": bas_dt,
        }
        try:
            r = requests.get(PRICE_API, params=params, timeout=30)
            r.raise_for_status()
            body = r.json().get("response", {}).get("body", {})
        except Exception as e:
            print(f" [API ERROR] {e}")
            break

        items = body.get("items", {})
        if not items:
            break
        item_list = items.get("item", [])
        if not item_list:
            break
        if isinstance(item_list, dict):
            item_list = [item_list]

        all_items.extend(item_list)
        total = int(body.get("totalCount", 0))
        if len(all_items) >= total:
            break
        page += 1
        time.sleep(0.2)

    return all_items


def _parse_item(item: dict, bas_dt: str) -> tuple[str, dict, dict] | None:
    """API 응답 item → (code, price_row, latest_info)."""
    code = (item.get("srtnCd") or "").strip()
    name = (item.get("itmsNm") or "").strip()
    if not code or not name:
        return None
    try:
        close  = float(item.get("clpr", 0) or 0)
        open_  = float(item.get("mkp",  0) or 0)
        high   = float(item.get("hipr", 0) or 0)
        low    = float(item.get("lopr", 0) or 0)
        volume = int(float(item.get("trqu", 0) or 0))
        flt_rt = float(item.get("fltRt", 0) or 0)
        mkt    = float(item.get("mrktTotAmt", 0) or 0)
    except (ValueError, TypeError):
        return None

    date_str = f"{bas_dt[:4]}-{bas_dt[4:6]}-{bas_dt[6:]}"
    price_row = {"code": code, "date": date_str,
                 "open": open_, "high": high, "low": low,
                 "close": close, "volume": volume}
    info = {"name": name, "close": close, "flt_rt": flt_rt, "mkt": mkt}
    return code, price_row, info


# ── DART ──────────────────────────────────────────────────────────────────────

def _dart_corp_codes() -> dict[str, str]:
    """DART corp_code.zip → {stock_code: corp_code} 매핑."""
    import io, zipfile
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    r = requests.get(url, params={"crtfc_key": DART_API_KEY}, timeout=30)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml_data = z.read("CORPCODE.xml").decode("utf-8")
    import re
    mapping: dict[str, str] = {}
    for m in re.finditer(
        r"<corp_code>(\w+)</corp_code>.*?<stock_code>(\w+)</stock_code>",
        xml_data, re.DOTALL
    ):
        corp, stock = m.group(1), m.group(2).strip()
        if stock:
            mapping[stock] = corp
    return mapping


def _dart_financials(corp_code: str) -> dict | None:
    year = date.today().year - 1
    url  = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
    params = {"crtfc_key": DART_API_KEY, "corp_code": corp_code,
              "bsns_year": str(year), "reprt_code": "11011"}
    try:
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
        if data.get("status") != "000":
            return None
        items = {i["account_nm"]: int(i["thstrm_amount"].replace(",", ""))
                 for i in data.get("list", [])
                 if i.get("thstrm_amount") and i["thstrm_amount"] != "-"}
        revenue = items.get("매출액") or items.get("수익(매출액)")
        op_profit = items.get("영업이익")
        equity = items.get("자본총계")
        net_income = items.get("당기순이익")
        roe = round(net_income / equity * 100, 1) if equity and net_income else None
        def fmt(v):
            if not v: return "-"
            if abs(v) >= 1e12: return f"{v/1e12:.1f}조"
            return f"{v/1e8:.0f}억"
        return {"revenue": fmt(revenue), "profit": fmt(op_profit),
                "roe": f"{roe}%" if roe else "-", "desc": ""}
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 수집 모드
# ══════════════════════════════════════════════════════════════════════════════

def cmd_seed(days: int = 35) -> None:
    """전체 상장 종목 날짜별 일괄 수집."""
    sb = _supabase()
    dates = _trading_dates(days)
    print(f"\n{'='*60}")
    print(f"[seed] 전체 상장 종목 × {len(dates)}일 수집 시작")
    print(f"       기간: {dates[0]} ~ {dates[-1]}")
    print(f"{'='*60}\n")

    # ── 1단계: 날짜별 전체 종목 시세 수집 ───────────────────────────────────
    prices_by_code: dict[str, list[dict]] = {}   # code → price rows
    latest_info:    dict[str, dict]       = {}   # code → 최신 info

    print("[1/3] 날짜별 전체 종목 시세 수집:")
    for i, bas_dt in enumerate(dates, 1):
        print(f"  [{i:02d}/{len(dates)}] {bas_dt} ...", end=" ", flush=True)
        items = fetch_all_for_date(bas_dt)
        if not items:
            print("✗ 휴장일 또는 오류")
            continue

        for item in items:
            parsed = _parse_item(item, bas_dt)
            if not parsed:
                continue
            code, price_row, info = parsed
            prices_by_code.setdefault(code, []).append(price_row)
            latest_info[code] = info  # 마지막 날짜 info가 최신

        print(f"✓ {len(items)}개 종목")
        time.sleep(0.4)

    total_stocks = len(prices_by_code)
    print(f"\n  → 총 {total_stocks}개 종목 수집 완료\n")

    # ── 2단계: stocks 먼저 적재 (FK 제약 때문에 stock_prices보다 먼저) ────────
    print(f"[2/3] stocks 지표 계산 + 적재 ({total_stocks}개):")
    stock_rows = []
    for code, prices in prices_by_code.items():
        info      = latest_info.get(code, {})
        name      = info.get("name", code)
        close_p   = int(info.get("close", 0))
        change_p  = round(info.get("flt_rt", 0), 2)
        mkt_won   = info.get("mkt", 0)
        mkt_cap   = round(mkt_won / 1e12, 2) if mkt_won else None

        meta      = STOCK_META.get(code, {})
        sector    = meta.get("sector", "기타")
        leader_c  = meta.get("leader", code)
        is_leader = (leader_c == code) and bool(meta)
        leader_nm = latest_info.get(leader_c, {}).get("name", name)

        indic = _calc_indicators(prices, is_leader)

        stock_rows.append({
            "code":                code,
            "name":                name,
            "sector":              sector,
            "is_leader":           is_leader,
            "leader_name":         leader_nm,
            "close_price":         close_p,
            "change_pct":          change_p,
            "market_cap_trillion": mkt_cap,
            "dividend_yield":      None,
            "listed_shares":       None,
            "financials":          {"revenue": "-", "profit": "-", "roe": "-", "desc": ""},
            "updated_at":          datetime.now(timezone.utc).isoformat(),
            **indic,
        })

    # stocks 벌크 upsert
    for i in range(0, len(stock_rows), 200):
        batch = stock_rows[i:i+200]
        sb.table("stocks").upsert(batch, on_conflict="code").execute()
        done = min(i + 200, len(stock_rows))
        print(f"  {done:,}/{len(stock_rows):,} 종목 ...", end="\r")

    print(f"  ✓ {len(stock_rows):,}개 완료           \n")

    # ── 3단계: stock_prices 벌크 적재 (stocks 적재 후) ───────────────────────
    print("[3/3] stock_prices 적재 중...")
    all_price_rows = [row for rows in prices_by_code.values() for row in rows]
    batch_size = 500
    for i in range(0, len(all_price_rows), batch_size):
        batch = all_price_rows[i:i+batch_size]
        sb.table("stock_prices").upsert(batch, on_conflict="code,date").execute()
        done = min(i + batch_size, len(all_price_rows))
        print(f"  {done:,}/{len(all_price_rows):,} 행 ...", end="\r")
    print(f"  ✓ {len(all_price_rows):,}행 완료           \n")

    print(f"{'='*60}")
    print("[seed] 전체 완료 ✓")
    print(f"{'='*60}\n")


def cmd_daily() -> None:
    """매일 cron: 최신 시세 업데이트."""
    sb = _supabase()
    dates = _trading_dates(5)
    print(f"[daily] 전체 종목 일일 업데이트 ({dates[-1]})")

    prices_by_code: dict[str, list[dict]] = {}
    latest_info:    dict[str, dict]       = {}

    for bas_dt in dates:
        items = fetch_all_for_date(bas_dt)
        if not items:
            continue
        for item in items:
            parsed = _parse_item(item, bas_dt)
            if not parsed:
                continue
            code, price_row, info = parsed
            prices_by_code.setdefault(code, []).append(price_row)
            latest_info[code] = info
        time.sleep(0.4)

    # stock_prices 업데이트
    all_price_rows = [row for rows in prices_by_code.values() for row in rows]
    for i in range(0, len(all_price_rows), 500):
        sb.table("stock_prices").upsert(
            all_price_rows[i:i+500], on_conflict="code,date"
        ).execute()
    print(f"  stock_prices ✓ {len(all_price_rows)}행")

    # stocks 업데이트 (지표 재계산)
    updated = 0
    for code, prices in prices_by_code.items():
        info     = latest_info.get(code, {})
        meta     = STOCK_META.get(code, {})
        is_leader = (meta.get("leader") == code) and bool(meta)
        indic    = _calc_indicators(prices, is_leader)
        mkt_won  = info.get("mkt", 0)
        sb.table("stocks").upsert({
            "code":                code,
            "name":                info.get("name", code),
            "close_price":         int(info.get("close", 0)),
            "change_pct":          round(info.get("flt_rt", 0), 2),
            "market_cap_trillion": round(mkt_won / 1e12, 2) if mkt_won else None,
            "sector":              meta.get("sector", "기타"),
            "is_leader":           is_leader,
            "updated_at":          datetime.now(timezone.utc).isoformat(),
            **indic,
        }, on_conflict="code").execute()
        updated += 1

    print(f"  stocks ✓ {updated}개")
    print("[daily] 완료 ✓")


def cmd_reindex() -> None:
    """RSI/buy_score만 재계산."""
    sb     = _supabase()
    stocks = sb.table("stocks").select("code, is_leader").execute().data or []
    print(f"[reindex] {len(stocks)}개 종목 지표 재계산")
    for s in stocks:
        code = s["code"]
        hist = (sb.table("stock_prices").select("close")
                .eq("code", code).order("date", desc=False)
                .limit(200).execute().data or [])
        if len(hist) < 5:
            continue
        prices = [{"close": float(h["close"])} for h in hist]
        indic  = _calc_indicators(prices, bool(s.get("is_leader")))
        sb.table("stocks").update({
            **indic, "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("code", code).execute()
    print(f"[reindex] 완료 ✓")


def cmd_cleanup(keep_days: int = 365) -> None:
    """1년(365일) 이전 stock_prices 데이터 삭제."""
    sb = _supabase()
    cutoff = (date.today() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    print(f"[cleanup] {cutoff} 이전 데이터 삭제 중...")
    result = sb.table("stock_prices").delete().lt("date", cutoff).execute()
    print(f"[cleanup] 완료 ✓ (기준일: {cutoff})")


def cmd_dart() -> None:
    """DART API로 재무 데이터 갱신."""
    sb     = _supabase()
    stocks = sb.table("stocks").select("code, name").execute().data or []
    print(f"[dart] {len(stocks)}개 종목 재무 수집")
    print("  corp_code 매핑 다운로드...", end=" ", flush=True)
    corp_map = _dart_corp_codes()
    print(f"✓ {len(corp_map)}개")
    for s in stocks:
        code, name = s["code"], s["name"]
        cc = corp_map.get(code)
        if not cc:
            continue
        fin = _dart_financials(cc)
        if fin:
            sb.table("stocks").update({"financials": fin}).eq("code", code).execute()
            print(f"  {name}({code}) ✓ 매출={fin['revenue']}")
        time.sleep(0.3)
    print("[dart] 완료 ✓")


def _gemini_classify_batch(batch: list[dict]) -> dict[str, str]:
    """Gemini로 종목 배치 → {code: sector} 반환."""
    import json as _json
    try:
        import google.generativeai as genai
    except ImportError:
        return {}

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        generation_config={"response_mime_type": "application/json"},
    )

    names_str = "\n".join(f"{s['code']}: {s['name']}" for s in batch)
    prompt = f"""한국 증권거래소(KOSPI/KOSDAQ) 상장 종목들을 아래 섹터 중 하나로 분류하세요.
모르거나 해당 없으면 "기타"로 분류하세요.

섹터 목록: {", ".join(SECTOR_LIST)}

종목 (코드: 이름):
{names_str}

JSON으로만 응답 (다른 말 없이): {{"종목코드": "섹터명", ...}}"""

    try:
        resp = model.generate_content(prompt)
        result = _json.loads(resp.text or "{}")
        # 유효한 섹터만 허용
        return {k: v for k, v in result.items() if v in SECTOR_LIST}
    except Exception as e:
        print(f" [Gemini 오류] {e}")
        return {}


def cmd_update_sectors() -> None:
    """Gemini AI로 전체 종목 섹터 자동 분류 후 Supabase 업데이트."""
    sb = _supabase()

    print(f"\n{'='*60}")
    print("[update-sectors] 전체 종목 섹터 AI 분류 시작")
    print(f"{'='*60}\n")

    # 1. 전체 종목 목록 가져오기
    all_stocks = sb.table("stocks").select("code, name").execute().data or []
    total = len(all_stocks)
    print(f"대상: {total:,}개 종목\n")

    # 2. Gemini 배치 분류 (80개씩)
    BATCH = 80
    all_updates: dict[str, str] = {}
    total_batches = (total + BATCH - 1) // BATCH

    for i in range(0, total, BATCH):
        batch = all_stocks[i:i + BATCH]
        batch_num = i // BATCH + 1
        print(f"  [{batch_num:02d}/{total_batches}] {batch[0]['name']} ~ {batch[-1]['name']} ...", end=" ", flush=True)

        result = _gemini_classify_batch(batch)
        all_updates.update(result)

        other_cnt = sum(1 for v in result.values() if v == "기타")
        print(f"✓ {len(result)}개 (기타: {other_cnt}개)")

        time.sleep(4.5)  # 15 RPM 제한 준수

    # STOCK_META 매핑으로 덮어쓰기 (curated 데이터 우선)
    for code, meta in STOCK_META.items():
        all_updates[code] = meta["sector"]

    print(f"\n  → 총 {len(all_updates):,}개 섹터 확정\n")

    # 3. 섹터별로 묶어서 UPDATE (upsert 대신 update + in_ 필터)
    print("[update-sectors] Supabase 업데이트 중...")
    from collections import defaultdict
    sector_to_codes: dict[str, list[str]] = defaultdict(list)
    for code, sector in all_updates.items():
        sector_to_codes[sector].append(code)

    total_updated = 0
    for sector, codes in sector_to_codes.items():
        # 500개씩 나눠서 IN 필터로 UPDATE
        for j in range(0, len(codes), 500):
            batch_codes = codes[j:j + 500]
            sb.table("stocks").update({"sector": sector}).in_("code", batch_codes).execute()
            total_updated += len(batch_codes)
        print(f"  {sector:12s}: {len(codes):,}개 ✓")

    print(f"\n  총 {total_updated:,}개 업데이트 완료")

    # 섹터별 집계 출력
    print("\n[섹터 분포]")
    from collections import Counter
    counts = Counter(all_updates.values())
    for sector, cnt in counts.most_common():
        print(f"  {sector:12s}: {cnt:,}개")

    print(f"\n{'='*60}")
    print("[update-sectors] 완료 ✓")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="StockNLP 데이터 수집기 (전체 상장 종목)")
    parser.add_argument("--seed",           action="store_true", help="최초 1회 전체 적재")
    parser.add_argument("--daily",          action="store_true", help="매일 최신 업데이트")
    parser.add_argument("--reindex",        action="store_true", help="RSI/buy_score 재계산만")
    parser.add_argument("--update-sectors", action="store_true", help="Gemini로 전체 종목 섹터 자동 분류")
    parser.add_argument("--cleanup",        action="store_true", help="1년 이전 시세 데이터 삭제")
    parser.add_argument("--dart",           action="store_true", help="DART 재무 갱신")
    parser.add_argument("--days",           type=int, default=35, help="수집 기간 (기본 35 영업일)")
    args = parser.parse_args()

    _require_env(for_dart=args.dart)

    if   args.seed:                        cmd_seed(days=args.days)
    elif args.daily:                       cmd_daily()
    elif args.reindex:                     cmd_reindex()
    elif getattr(args, "update_sectors"):  cmd_update_sectors()
    elif args.cleanup:                     cmd_cleanup()
    elif args.dart:                        cmd_dart()
    else:
        parser.print_help()
        print("\n예시: python data_collector.py --seed")


if __name__ == "__main__":
    main()
