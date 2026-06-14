-- PostgreSQL: Create daily_sentiment_summary table
CREATE TABLE IF NOT EXISTS daily_sentiment_summary (
    date DATE NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    avg_sentiment FLOAT,
    positive_count INTEGER,
    negative_count INTEGER,
    neutral_count INTEGER,
    total_articles INTEGER,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, ticker)
);

-- BigQuery: Create daily_sentiment_summary table
CREATE TABLE IF NOT EXISTS `stock-market-pipeline.ngx_market_data.daily_sentiment_summary` (
    date DATE,
    ticker STRING,
    avg_sentiment FLOAT64,
    positive_count INT64,
    negative_count INT64,
    neutral_count INT64,
    total_articles INT64,
    ingested_at TIMESTAMP
);

-- Replace `your_project.your_dataset` with your actual BigQuery project and dataset names.