"""Refresh local data artifacts used by the FastAPI app.

Usage:
    python scripts/refresh_data.py --prices --macro --news
    python scripts/refresh_data.py --news-only
    python scripts/refresh_data.py --rebuild-nlp
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.news_sentiment import (
    build_daily_sentiment_summary,
    load_daily_sentiment_summary,
    load_news_articles,
    save_daily_sentiment_summary,
)
from app.services.model_snapshot import get_model_signal_snapshot
from app.routers.recommendations import _cached_ai_insights
PIPELINE_PATH = PROJECT_ROOT / "data" / "pipeline.py"
SNAPSHOTS = [
    PROJECT_ROOT / "models" / "model_signal_snapshot.json",
    PROJECT_ROOT / "models" / "ai_insights_snapshot.json",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh NGX app data artifacts")
    parser.add_argument("--prices", action="store_true", help="Run daily price refresh")
    parser.add_argument("--macro", action="store_true", help="Run macro refresh")
    parser.add_argument("--news", action="store_true", help="Run news fetchers")
    parser.add_argument("--news-only", action="store_true", help="Run news fetchers and NLP only")
    parser.add_argument("--rebuild-nlp", action="store_true", help="Rebuild sentiment summaries from existing articles")
    args = parser.parse_args()

    if args.prices:
        _pipeline().daily()
    if args.macro:
        _pipeline().macro()
    if args.news or args.news_only:
        _pipeline().news()
    if args.rebuild_nlp or args.news or args.news_only:
        rebuild_nlp()

    clear_app_caches()
    print("Refresh complete.")


def rebuild_nlp() -> None:
    """Recompute daily ticker sentiment from processed article parquet files."""

    load_news_articles.cache_clear()
    load_daily_sentiment_summary.cache_clear()
    summary = build_daily_sentiment_summary()
    save_daily_sentiment_summary(summary)
    load_daily_sentiment_summary.cache_clear()
    print(f"NLP summary rows: {len(summary)}")


def clear_app_caches() -> None:
    """Remove stale model/AI snapshots and clear in-process caches."""

    for path in SNAPSHOTS:
        path.unlink(missing_ok=True)
    get_model_signal_snapshot.cache_clear()
    _cached_ai_insights.cache_clear()


def _pipeline():
    """Load the legacy data/pipeline.py module despite data/pipeline package name."""

    spec = importlib.util.spec_from_file_location("ngx_pipeline_main", PIPELINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load pipeline module from {PIPELINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    main()
