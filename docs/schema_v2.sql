-- =========================================================
-- StockNLP Schema v2 — 기존 schema.sql 실행 후 이걸 추가 실행
-- Supabase SQL Editor에 붙여넣고 Run
-- =========================================================

-- stocks 테이블에 새 컬럼 추가
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS market_cap_trillion FLOAT;
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS dividend_yield      FLOAT;
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS listed_shares       BIGINT;

-- ── 지수 시세 테이블 (KOSPI / KOSDAQ / KRX300 등) ─────────────────────
CREATE TABLE IF NOT EXISTS market_indices (
    idx_code   TEXT NOT NULL,   -- 'KOSPI', 'KOSDAQ', 'KRX300' 등
    idx_name   TEXT NOT NULL,
    date       DATE NOT NULL,
    close      FLOAT,
    change_pct FLOAT,
    PRIMARY KEY (idx_code, date)
);
CREATE INDEX IF NOT EXISTS idx_market_indices_date ON market_indices (date DESC);

-- ── 일반상품 시세 테이블 (금/원유/구리 등) ───────────────────────────
CREATE TABLE IF NOT EXISTS commodities (
    code       TEXT NOT NULL,   -- 상품 단축코드 또는 이름 slug
    name       TEXT NOT NULL,
    date       DATE NOT NULL,
    close      FLOAT,
    unit       TEXT,            -- '원/g', '달러/배럴' 등
    PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_commodities_date ON commodities (date DESC);
