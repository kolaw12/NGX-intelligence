# Data Schemas

Column contracts for every dataset produced by the data layer.
ML / Data Engineers: load with the snippets shown.

---

## 1. master/tickers.csv

The authoritative list of NGX-listed companies covered.

| Column      | Type | Example                                                | Notes                  |
|-------------|------|--------------------------------------------------------|------------------------|
| ticker      | str  | GTB                                                    | BroadStreet symbol     |
| name        | str  | Guaranty Trust Holding Company Plc                     | Full registered name   |
| sector      | str  | Banking                                                | Human-readable         |
| sector_id   | int  | 5                                                      | BroadStreet sector ID  |
| detail_url  | str  | /compDetail.php?s=GTB&p=qs                             | Canonical fetch path (append BASE_URL) |

```python
pd.read_csv("data/master/tickers.csv")
```

---

## 2. processed/prices/historical/<TICKER>.parquet

Daily OHLCV per stock. Backfilled from 1991 (or first listing) to latest trade date.

| Column  | Type    | Example     | Notes                            |
|---------|---------|-------------|----------------------------------|
| date    | date    | 2026-05-13  | Trading date (NGX calendar)      |
| pclose  | float64 | 151.95      | Previous close                   |
| high    | float64 | 150.00      | Day high                         |
| low     | float64 | 147.00      | Day low                          |
| close   | float64 | 147.50      | Day close (primary price)        |
| volume  | int64   | 9924451     | Shares traded                    |
| change  | float64 | -4.45       | close - pclose                   |

Index: `date` (sorted ascending, no duplicates).

```python
pd.read_parquet("data/output/processed/prices/historical/GTB.parquet")
```

---

## 3. processed/prices/snapshots/<YYYY-MM-DD>.parquet

One row per ticker for that trading day. Combine with tickers.csv on `ticker`.

| Column       | Type    | Example      |
|--------------|---------|--------------|
| ticker       | str     | GTB          |
| date         | date    | 2026-05-14   |
| last_trade   | float64 | 147.50       |
| change       | float64 | -4.45        |
| prev_close   | float64 | 151.95       |
| open         | float64 | 151.95       |
| day_high     | float64 | 150.00       |
| day_low      | float64 | 147.00       |
| volume       | int64   | 9924451      |
| avg_vol_3mo  | float64 | 27668861.44  |

---

## 4. processed/fundamentals/<YYYY-MM-DD>.parquet

| Column      | Type    | Example     | Notes                            |
|-------------|---------|-------------|----------------------------------|
| ticker      | str     | GTB         |                                  |
| date        | date    | 2026-05-14  |                                  |
| mkt_cap_m   | float64 | 5035502.50  | Market cap, millions of NGN      |
| pe          | float64 | 5.0         | Price / Earnings                 |
| eps         | float64 | 29.81       | Earnings per share               |
| div_yield   | float64 | 5.44        | Percentage                       |
| week52_low  | float64 | 66.60       |                                  |
| week52_high | float64 | 156.95      |                                  |

---

## 5. processed/macro/exchange_rates_<DATE>.parquet

Planned. Currently blocked by JS-rendering on BroadStreet's exchange-rate page.
Likely future source: CBN official rates.

---

## Update cadence

| Dataset           | Refresh       | Command                              |
|-------------------|---------------|--------------------------------------|
| master/tickers    | Monthly       | `python -m data.pipeline discover`   |
| prices/historical | Once + daily  | `backfill` then `daily`              |
| prices/snapshots  | Daily         | `python -m data.pipeline daily`      |
| fundamentals      | Daily         | rolled into `daily`                  |
