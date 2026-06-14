# test_pipeline.py
# Run this to verify the pipeline is working correctly
# python test_pipeline.py

import json
import os
import pandas as pd
from pathlib import Path

os.environ.setdefault("NUPAT_DISABLE_FINBERT", "1")

from sentiment_pipeline import (
    TICKER_ALIASES,
    clean_text,
    find_tickers,
    process_headline,
    aggregate_one_stock,
    prepare_articles,
)

passed = 0
failed = 0

def check(test_name, condition, expected, got):
    global passed, failed
    if condition:
        print(f"  PASS — {test_name}")
        passed += 1
    else:
        print(f"  FAIL — {test_name}")
        print(f"         Expected : {expected}")
        print(f"         Got      : {got}")
        failed += 1


print("\n" + "=" * 55)
print("  NUPAT AI — PIPELINE TESTS")
print("=" * 55)

# ─────────────────────────────────────────
# TEST GROUP 1 — clean_text()
# ─────────────────────────────────────────
print("\n[ clean_text() ]\n")

result = clean_text("<div>Zenith Bank profit rises 3.2%</div>")
check(
    "Removes HTML tags",
    "<div>" not in result,
    "no HTML tags",
    result
)

result = clean_text("MTN Nigeria 🚀📊 records growth")
check(
    "Removes emojis",
    "🚀" not in result and "📊" not in result,
    "no emojis",
    result
)

result = clean_text("https://businessday.ng/article Access Bank falls")
check(
    "Removes URLs",
    "https://" not in result,
    "no URL",
    result
)

result = clean_text("UBA &amp; FBN report strong results &nbsp;")
check(
    "Removes HTML entities",
    "&amp;" not in result and "&nbsp;" not in result,
    "no HTML entities",
    result
)

result = clean_text("  Dangote   Cement  \n\n  falls  ")
check(
    "Collapses whitespace",
    "  " not in result and "\n" not in result,
    "single spaces only",
    result
)

# ─────────────────────────────────────────
# TEST GROUP 2 — find_tickers()
# ─────────────────────────────────────────
print("\n[ find_tickers() ]\n")

result = find_tickers("Zenith Bank reports strong Q2 profit")
check(
    "Detects Zenith Bank → ZEN",
    "ZEN" in result,
    ["ZEN"],
    result
)

result = find_tickers("Guaranty Trust reports N500bn profit")
check(
    "Detects Guaranty Trust → GTB",
    "GTB" in result,
    ["GTB"],
    result
)

result = find_tickers("Access Holdings raises concern over loan defaults")
check(
    "Detects Access Holdings → ABL",
    "ABL" in result,
    ["ABL"],
    result
)

result = find_tickers("CBN holds interest rate at 26.25 percent")
check(
    "Returns empty list for macro headline",
    result == [],
    [],
    result
)

result = find_tickers("UBA and Fidelity Bank both report strong results")
check(
    "Detects multiple tickers in one headline",
    "UBA" in result and "FID" in result,
    ["UBA", "FID"],
    result
)

result = find_tickers("Academy Press posts stronger earnings after cost savings")
check(
    "Detects CSV-derived alias Academy Press → ACP",
    "ACP" in result,
    ["ACP"],
    result
)

result = find_tickers("All stocks opened higher after NGX market rally")
check(
    "Does not treat common word 'all' as ticker ALL",
    "ALL" not in result,
    "no ALL false positive",
    result
)

check(
    "Ticker CSV aliases are loaded",
    len(TICKER_ALIASES) > 250,
    "more than 250 aliases",
    len(TICKER_ALIASES)
)

# ─────────────────────────────────────────
# TEST GROUP 3 — keyword_boost()
# ─────────────────────────────────────────
print("\n[ keyword_boost() ]\n")

result = process_headline("Guaranty Trust reports N500bn profit in H1 2026")
check(
    "Boosts NEUTRAL to POSITIVE for clear profit headline",
    result['sentiment'] == "positive",
    "positive",
    result['sentiment']
)

result = process_headline("Dangote Cement volume falls as construction slows")
check(
    "Keeps NEGATIVE for clear negative headline",
    result['sentiment'] == "negative",
    "negative",
    result['sentiment']
)

result = process_headline("Fidelity Bank shares rise 4 percent on strong results")
check(
    "Detects positive sentiment for rising shares",
    result['sentiment'] == "positive",
    "positive",
    result['sentiment']
)

# ─────────────────────────────────────────
# TEST GROUP 4 — prepare_articles()
# ─────────────────────────────────────────
print("\n[ prepare_articles() ]\n")

# Simulate a pre-tagged NGX article
ngx_row = pd.DataFrame([{
    "headline"         : "Zenith Bank Plc — Audited Full Year Results",
    "article_text"     : "Zenith Bank profit increased 22 percent to N620 billion.",
    "source"           : "ngx_announcements",
    "ticker_mode"      : "pre_tagged",
    "mentioned_tickers": ["ZEN"],
}])

prepared = prepare_articles(ngx_row)
check(
    "Pre-tagged NGX article uses existing ticker directly",
    prepared[0]['tickers'] == ["ZEN"],
    ["ZEN"],
    prepared[0]['tickers']
)

# Simulate a BusinessDay article needing tagging
bd_row = pd.DataFrame([{
    "headline"         : "Zenith Bank reports strong Q2 profit",
    "article_text"     : "Full article body here.",
    "source"           : "businessday",
    "ticker_mode"      : "needs_tagging",
    "mentioned_tickers": [],
}])

prepared = prepare_articles(bd_row)
check(
    "BusinessDay article runs find_tickers() on headline",
    "ZEN" in prepared[0]['tickers'],
    ["ZEN"],
    prepared[0]['tickers']
)

# ─────────────────────────────────────────
# TEST GROUP 5 — aggregate_one_stock()
# ─────────────────────────────────────────
print("\n[ aggregate_one_stock() ]\n")

# All positive headlines should give positive signal
positive_headlines = [
    "Zenith Bank profit rises strongly beating all estimates",
    "Zenith Bank declares dividend for shareholders",
    "Zenith Bank digital growth accelerates in H1",
    "Zenith Bank revenue up 34 percent year on year",
]
result = aggregate_one_stock("ZEN", positive_headlines)
check(
    "All positive headlines → POSITIVE signal",
    result['signal'] == "POSITIVE",
    "POSITIVE",
    result['signal']
)

# All negative headlines should give negative signal
negative_headlines = [
    "Zenith Bank faces regulatory probe over FX losses",
    "Zenith Bank NPL ratio rises amid loan defaults",
    "Zenith Bank shares fall on weak earnings outlook",
    "Zenith Bank under CBN scrutiny for compliance failures",
]
result = aggregate_one_stock("ZEN", negative_headlines)
check(
    "All negative headlines → NEGATIVE signal",
    result['signal'] == "NEGATIVE",
    "NEGATIVE",
    result['signal']
)

# Single headline should have confidence penalty applied
result = aggregate_one_stock("ZEN", ["Zenith Bank profit rises strongly"])
check(
    "Single headline score is penalised (below 0.9)",
    abs(result['final_score']) < 0.9,
    "score < 0.9 due to penalty",
    result['final_score']
)

# Empty input should return neutral
result = aggregate_one_stock("ZEN", [])
check(
    "Empty headline list returns NEUTRAL",
    result['signal'] == "NEUTRAL" and result['final_score'] == 0.0,
    "NEUTRAL, 0.0",
    f"{result['signal']}, {result['final_score']}"
)

# ─────────────────────────────────────────
# TEST GROUP 6 — JSON export structure
# ─────────────────────────────────────────
print("\n[ export_for_backend() — JSON structure ]\n")

export_files = list(Path(".").glob("nupat_daily_package_*.json"))
if export_files:
    with open(export_files[-1]) as f:
        package = json.load(f)

    check(
        "Package contains 'date' key",
        "date" in package,
        True,
        "date" in package
    )
    check(
        "Package contains 'stock_sentiments' list",
        isinstance(package.get("stock_sentiments"), list),
        "list",
        type(package.get("stock_sentiments"))
    )
    check(
        "Each stock entry has ticker, score, and signal",
        all(
            "ticker" in s and "sentiment_score" in s and "signal" in s
            for s in package["stock_sentiments"]
        ),
        True,
        "checking all entries"
    )
    check(
        "All sentiment scores are between -1.0 and +1.0",
        all(
            -1.0 <= s["sentiment_score"] <= 1.0
            for s in package["stock_sentiments"]
        ),
        True,
        "all within range"
    )
    check(
        "All signals are valid values",
        all(
            s["signal"] in ["POSITIVE", "NEUTRAL", "NEGATIVE"]
            for s in package["stock_sentiments"]
        ),
        True,
        "checking all signals"
    )
else:
    print("  SKIP — no export file found yet. Run sentiment_pipeline.py first.")

# ─────────────────────────────────────────
# FINAL SCORE
# ─────────────────────────────────────────
total = passed + failed
print(f"\n{'=' * 55}")
print(f"  Results: {passed}/{total} tests passed")
if failed == 0:
    print(f"  All tests passed — pipeline is working correctly")
else:
    print(f"  {failed} test(s) failed — review output above")
print(f"{'=' * 55}\n")
