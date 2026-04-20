-- =========================================================
-- StockNLP 전체 스키마 (schema.sql + schema_v2.sql 통합본)
-- Supabase → SQL Editor → 이 파일 전체 붙여넣기 → Run
-- =========================================================

-- 1. 종목 테이블
CREATE TABLE IF NOT EXISTS stocks (
    code                 TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    sector               TEXT,
    is_leader            BOOLEAN DEFAULT false,
    leader_name          TEXT,
    close_price          INTEGER,
    change_pct           FLOAT,
    rsi                  INTEGER,
    rsi_prev             INTEGER,
    buy_score            INTEGER DEFAULT 0,
    profit_growth_years  INTEGER DEFAULT 0,
    market_cap_trillion  FLOAT,
    dividend_yield       FLOAT,
    listed_shares        BIGINT,
    financials           JSONB,
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stocks_sector      ON stocks (sector);
CREATE INDEX IF NOT EXISTS idx_stocks_buy_score   ON stocks (buy_score DESC);
CREATE INDEX IF NOT EXISTS idx_stocks_is_leader   ON stocks (is_leader) WHERE is_leader = true;

-- 2. 일별 가격 테이블
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

-- 3. 지수 시세 테이블 (KOSPI / KOSDAQ / KRX300)
CREATE TABLE IF NOT EXISTS market_indices (
    idx_code   TEXT NOT NULL,
    idx_name   TEXT NOT NULL,
    date       DATE NOT NULL,
    close      FLOAT,
    change_pct FLOAT,
    PRIMARY KEY (idx_code, date)
);
CREATE INDEX IF NOT EXISTS idx_market_indices_date ON market_indices (date DESC);

-- 4. 일반상품 시세 테이블 (금/원유/구리)
CREATE TABLE IF NOT EXISTS commodities (
    code       TEXT NOT NULL,
    name       TEXT NOT NULL,
    date       DATE NOT NULL,
    close      FLOAT,
    unit       TEXT,
    PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_commodities_date ON commodities (date DESC);

-- 5. 검색 기록
CREATE TABLE IF NOT EXISTS search_history (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    query_text   TEXT NOT NULL,
    filters      JSONB,
    result_count INTEGER,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_search_history_created ON search_history (created_at DESC);

-- 6. 북마크
CREATE TABLE IF NOT EXISTS bookmarks (
    id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code       TEXT NOT NULL REFERENCES stocks(code) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (code)
);
