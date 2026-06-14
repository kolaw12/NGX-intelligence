-- PostgreSQL schema for the NGX warehouse (app/API serving store).
-- Run with: psql "<conn>" -f app/db/schema.sql  OR paste into pgAdmin Query Tool.

CREATE TABLE IF NOT EXISTS price (
    date        DATE NOT NULL,
    ticker      TEXT              NOT NULL,
    pclose      DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      BIGINT,
    change      DOUBLE PRECISION,
    ingested_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_price_ticker_date ON price (ticker, date DESC);
