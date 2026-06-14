"""
Piece 2 - reconcile raw corporate actions against the price series.

The raw bonus records carry a fiscal-year-end date (not the ex-date) and an
ambiguous ratio text ('4 for 1'). Rather than trust the text, we let the PRICE
be ground truth:

  - NGX has a +/-10% daily price limit, so any single-day drop > 10% is almost
    certainly a corporate action, not normal trading.
  - In the months after each declaration we find the largest such drop
    (excluding the known 2010-08-05 corrupt cluster and absurd >95% "drops"
    that are data errors). That drop's DATE is the true ex-date, and its
    magnitude IS the adjustment factor.
  - We store the EMPIRICAL ratio implied by the actual drop
    (ratio = 1/drop - 1), so fct_price_adjusted (factor = 1/(1+ratio) = drop)
    reverses exactly the observed jump. The nominal text is kept only as a
    sanity note.
  - Bonuses with no qualifying drop are FLAGGED for manual review, never
    auto-applied.

Cash dividends are skipped (v1 adjustment is a no-op for them).

DRY-RUN by default: prints a report + a proposed CSV. Only `--write-seed`
appends accepted rows to dbt/seeds/corporate_actions.csv.

Usage (from ai-stock-broker-backend):
    python -m scripts.reconcile_corporate_actions
    python -m scripts.reconcile_corporate_actions --write-seed
"""
import argparse
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import pandas as pd
from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from app.services.warehouse import get_warehouse  # noqa: E402

RAW = BACKEND_ROOT / "data/output/processed/corporate_actions/raw_corporate_actions.parquet"
PROPOSED = BACKEND_ROOT / "data/output/processed/corporate_actions/reconciled_proposed.csv"
FLAGGED = BACKEND_ROOT / "data/output/processed/corporate_actions/flagged_for_review.csv"
SEED = BACKEND_ROOT / "dbt/seeds/corporate_actions.csv"

WINDOW_DAYS = 270          # ex-date is within ~9 months after fiscal year-end
DROP_MIN, DROP_MAX = 0.05, 0.90   # factor band: >10% fall (CA) but not >95% (corruption)
CORRUPT_DATES = ["2010-08-05"]    # documented bad cluster (KNOWN_ISSUES §11)


def parse_nominal(raw_value: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*for\s*(\d+(?:\.\d+)?)", str(raw_value), re.I)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def _bq_prices(tickers):
    wh = get_warehouse()
    bq = getattr(wh, "bq", wh)
    tlist = ", ".join(f"'{t}'" for t in tickers)
    bad = ", ".join(f"DATE '{d}'" for d in CORRUPT_DATES)
    q = (f"SELECT date, ticker, close FROM "
         f"`{bq.project_id}.{bq.market_dataset}.price` "
         f"WHERE ticker IN ({tlist}) AND close > 0 "
         f"AND date NOT IN ({bad}) ORDER BY ticker, date")
    df = bq.client.query(q).to_dataframe()
    df["date"] = pd.to_datetime(df["date"])
    return df


def reconcile():
    if not RAW.exists():
        sys.exit(f"ERROR: {RAW} not found. Run `python -m data.pipeline "
                 f"corporate-actions` first.")
    raw = pd.read_parquet(RAW)
    bonuses = raw[raw["action_type"] == "bonus"].copy()
    if bonuses.empty:
        print("No bonus rows to reconcile.")
        return pd.DataFrame()
    bonuses["declared_date"] = pd.to_datetime(bonuses["declared_date"])
    prices = _bq_prices(sorted(bonuses["ticker"].unique()))

    rows, flags = [], []
    for _, b in bonuses.sort_values(["ticker", "declared_date"]).iterrows():
        tk, decl, raw_val = b["ticker"], b["declared_date"], b["raw_value"]
        px = prices[(prices["ticker"] == tk) &
                    (prices["date"] > decl) &
                    (prices["date"] <= decl + pd.Timedelta(days=WINDOW_DAYS))].copy()
        if px.empty:
            flags.append({"ticker": tk, "declared_date": decl.date().isoformat(),
                          "raw_value": raw_val, "reason": "no_price_window"})
            continue
        px = px.sort_values("date")
        px["drop"] = px["close"] / px["close"].shift()
        cand = px[(px["drop"] >= DROP_MIN) & (px["drop"] < DROP_MAX)]
        if cand.empty:
            # how close did the biggest fall get? helps triage small bonuses
            mn = px["drop"].min()
            reason = ("corrupt_only_drop" if pd.notna(mn) and mn < DROP_MIN
                      else f"max_fall_only_{(1-mn)*100:.0f}pct" if pd.notna(mn)
                      else "no_drop_data")
            flags.append({"ticker": tk, "declared_date": decl.date().isoformat(),
                          "raw_value": raw_val, "reason": reason})
            continue
        best = cand.loc[cand["drop"].idxmin()]
        drop_f = float(best["drop"])
        emp_ratio = (1.0 / drop_f) - 1.0
        rows.append({
            "ticker": tk, "ex_date": best["date"].date().isoformat(),
            "action_type": "bonus", "ratio": round(emp_ratio, 6), "dividend": "",
            "source": "broadstreet_reconciled",
            "notes": f"nominal '{raw_val}' declared {decl.date()}; price x{drop_f:.3f}",
        })

    proposed, flagged = pd.DataFrame(rows), pd.DataFrame(flags)
    PROPOSED.parent.mkdir(parents=True, exist_ok=True)
    proposed.to_csv(PROPOSED, index=False)
    flagged.to_csv(FLAGGED, index=False)
    print(f"Total bonuses: {len(bonuses)}  |  MATCHED: {len(proposed)}  |  "
          f"FLAGGED: {len(flagged)}")
    if not flagged.empty:
        print("\nFlag reasons:")
        print(flagged["reason"].value_counts().to_string())
    print(f"\nmatched -> {PROPOSED}\nflagged -> {FLAGGED}")
    return proposed


def write_seed(proposed: pd.DataFrame):
    if proposed.empty:
        print("Nothing to write to the seed.")
        return
    existing = pd.read_csv(SEED)
    merged = (pd.concat([existing, proposed], ignore_index=True)
              .drop_duplicates(subset=["ticker", "ex_date"], keep="last"))
    merged.to_csv(SEED, index=False)
    print(f"Appended {len(proposed)} reconciled bonus row(s) to {SEED}.")
    print("Next: dbt build, then validate adj_close continuity at each ex-date.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-seed", action="store_true")
    args = ap.parse_args()
    proposed = reconcile()
    if args.write_seed:
        write_seed(proposed)
    else:
        print("\nDRY-RUN. Review the proposed CSV, then re-run with --write-seed.")


if __name__ == "__main__":
    main()
