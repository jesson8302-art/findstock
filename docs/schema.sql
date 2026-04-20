-- =========================================================
-- StockNLP Supabase Schema (MVP)
-- =========================================================
-- 실행: Supabase 프로젝트 → SQL Editor → 전체 붙여넣고 Run
-- =========================================================

-- 1. 종목 테이블
CREATE TABLE IF NOT EXISTS stocks (
    code                 TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    sector               TEXT,
    is_leader            BOOLEAN DEFAULT false,
    leader_name          TEXT,

    -- 최신 시세 스냅샷
    close_price          INTEGER,
    change_pct           FLOAT,

    -- 지표 (reindex 시 채워짐)
    rsi                  INTEGER,
    rsi_prev             INTEGER,
    buy_score            INTEGER DEFAULT 0,
    profit_growth_years  INTEGER DEFAULT 0,

    -- 재무 요약 (JSON 형태 — revenue/profit/roe/desc 키)
    financials           JSONB,

    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stocks_sector      ON stocks (sector);
CREATE INDEX IF NOT EXISTS idx_stocks_buy_score   ON stocks (buy_score DESC);
CREATE INDEX IF NOT EXISTS idx_stocks_is_leader   ON stocks (is_leader) WHERE is_leader = true;

-- 2. 일별 가격 테이블 (차트 / 지표 계산용)
CREATE TABLE IF NOT EXISTS stock_prices (
    code      TEXT NOT NULL REFERENCES stocks(code) ON DELETE CASCADE,
    date      DATE NOT NULL,
    open      FLOAT,
    high      FLOAT,
    low       FLOAT,
    close     FLOAT,
    volume    BIGINT,
    PRIMARY KEY (code, date)
);

CREATE INDEX IF NOT EXISTS idx_prices_code_date_desc ON stock_prices (code, date DESC);

-- 3. 검색 기록 (마이페이지용)
CREATE TABLE IF NOT EXISTS search_history (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    query_text   TEXT NOT NULL,
    filters      JSONB,
    result_count INTEGER,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_history_created ON search_history (created_at DESC);

-- 4. 북마크
CREATE TABLE IF NOT EXISTS bookmarks (
    id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code       TEXT NOT NULL REFERENCES stocks(code) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (code)
);

-- =========================================================
-- (선택) RLS: anon 키로 읽기만 허용하고 싶을 때
-- =========================================================
-- ALTER TABLE stocks ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "read stocks" ON stocks FOR SELECT USING (true);
-- ALTER TABLE stock_prices ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "read prices" ON stock_prices FOR SELECT USING (true);
