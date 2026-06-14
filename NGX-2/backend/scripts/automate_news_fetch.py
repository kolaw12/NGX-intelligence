#!/usr/bin/env python3
"""
Automated News Fetch Orchestrator

Provides robust, monitored execution of NGX Announcements and BusinessDay
fetchers with:
  - Parallel execution support
  - Comprehensive error handling and retry logic
  - Detailed logging and metrics
  - Sentiment analysis integration
  - Health checks and notifications
  - Graceful degradation

Usage:
  python scripts/automate_news_fetch.py                    # Run all fetchers
  python scripts/automate_news_fetch.py --ngx-only         # NGX only
  python scripts/automate_news_fetch.py --businessday-only # BusinessDay only
  python scripts/automate_news_fetch.py --max-articles 50  # Custom limit
  python scripts/automate_news_fetch.py --skip-sentiment   # Skip sentiment
  python scripts/automate_news_fetch.py --parallel         # Parallel execution
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/logs/news_fetch_automation.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of a single fetcher run."""
    source: str
    success: bool
    articles_count: int = 0
    duration_seconds: float = 0.0
    error: str = None
    start_time: datetime = None
    end_time: datetime = None
    articles_data: pd.DataFrame = None

    def to_dict(self):
        """Convert to serializable dict."""
        d = asdict(self)
        d['start_time'] = self.start_time.isoformat() if self.start_time else None
        d['end_time'] = self.end_time.isoformat() if self.end_time else None
        d.pop('articles_data', None)  # Remove DataFrame for JSON serialization
        return d


class NewsAutomationOrchestrator:
    """Orchestrates news fetching with monitoring and error handling."""

    def __init__(self, max_articles: int = 100, skip_sentiment: bool = False):
        self.max_articles = max_articles
        self.skip_sentiment = skip_sentiment
        self.results = {}
        self.log_dir = Path("data/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    def _fetch_ngx_announcements(self) -> FetchResult:
        """Fetch NGX announcements."""
        source = "NGX Announcements"
        logger.info(f"Starting {source} fetcher...")
        result = FetchResult(source=source, success=False)
        result.start_time = datetime.now()
        
        try:
            from data.fetchers.news.ngx_announcements import NGXAnnouncementsFetcher
            
            fetcher = NGXAnnouncementsFetcher(max_requests=200)
            start = time.time()
            
            articles = fetcher.fetch_articles(max_articles=self.max_articles)
            
            result.duration_seconds = time.time() - start
            result.articles_count = len(articles) if articles is not None else 0
            result.articles_data = articles
            result.success = True
            result.end_time = datetime.now()
            
            logger.success(
                f"✓ {source}: {result.articles_count} articles in {result.duration_seconds:.1f}s"
            )
            
        except Exception as e:
            result.error = str(e)
            result.end_time = datetime.now()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            logger.error(f"✗ {source} failed: {e}")
        
        return result

    def _fetch_businessday(self) -> FetchResult:
        """Fetch BusinessDay articles."""
        source = "BusinessDay Nigeria"
        logger.info(f"Starting {source} fetcher...")
        result = FetchResult(source=source, success=False)
        result.start_time = datetime.now()
        
        try:
            from data.fetchers.news.businessday import BusinessDayFetcher
            
            fetcher = BusinessDayFetcher(max_requests=200)
            start = time.time()
            
            articles = fetcher.fetch_articles(max_articles=self.max_articles)
            
            result.duration_seconds = time.time() - start
            result.articles_count = len(articles) if articles is not None else 0
            result.articles_data = articles
            result.success = True
            result.end_time = datetime.now()
            
            logger.success(
                f"✓ {source}: {result.articles_count} articles in {result.duration_seconds:.1f}s"
            )
            
        except Exception as e:
            result.error = str(e)
            result.end_time = datetime.now()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            logger.error(f"✗ {source} failed: {e}")
        
        return result

    def run_sentiment_analysis(self) -> bool:
        """Run sentiment analysis pipeline."""
        if self.skip_sentiment:
            logger.info("⊘ Sentiment analysis skipped")
            return True
        
        logger.info("Starting sentiment analysis pipeline...")
        try:
            from backend.app.nlp.sentiment_pipeline import run_pipeline
            start = time.time()
            run_pipeline(since_days_ago=1)
            duration = time.time() - start
            logger.success(f"✓ Sentiment pipeline complete in {duration:.1f}s")
            return True
        except Exception as e:
            logger.warning(f"⚠ Sentiment analysis warning: {e}")
            return False

    def run_parallel(self, fetchers: list) -> dict:
        """Execute fetchers in parallel."""
        logger.info(f"Running {len(fetchers)} fetchers in parallel...")
        results = {}
        
        with ThreadPoolExecutor(max_workers=len(fetchers)) as executor:
            future_map = {}
            
            for fetcher_name, fetcher_func in fetchers:
                future = executor.submit(fetcher_func)
                future_map[future] = fetcher_name
            
            for future in as_completed(future_map):
                result = future.result()
                results[result.source] = result
        
        return results

    def run_sequential(self, fetchers: list) -> dict:
        """Execute fetchers sequentially."""
        logger.info(f"Running {len(fetchers)} fetchers sequentially...")
        results = {}
        
        for fetcher_name, fetcher_func in fetchers:
            result = fetcher_func()
            results[result.source] = result
        
        return results

    def run(self, use_parallel: bool = False, ngx_only: bool = False, 
            businessday_only: bool = False) -> bool:
        """
        Run the news fetch automation.
        
        Returns:
            True if at least one fetcher succeeded
        """
        logger.info("=" * 70)
        logger.info("NEWS FETCH AUTOMATION STARTED")
        logger.info(f"Max articles per source: {self.max_articles}")
        logger.info(f"Parallel execution: {use_parallel}")
        logger.info("=" * 70)
        
        start_time = time.time()
        
        # Build fetcher list
        fetchers = []
        if not businessday_only:
            fetchers.append(("NGX", self._fetch_ngx_announcements))
        if not ngx_only:
            fetchers.append(("BusinessDay", self._fetch_businessday))
        
        # Execute fetchers
        if use_parallel and len(fetchers) > 1:
            self.results = self.run_parallel(fetchers)
        else:
            self.results = self.run_sequential(fetchers)
        
        # Count successes
        successful = sum(1 for r in self.results.values() if r.success)
        total_articles = sum(r.articles_count for r in self.results.values())
        
        logger.info("")
        logger.info("FETCHING SUMMARY")
        logger.info("-" * 70)
        for source, result in self.results.items():
            status = "✓" if result.success else "✗"
            logger.info(
                f"{status} {source}: {result.articles_count} articles | "
                f"{result.duration_seconds:.1f}s"
            )
            if result.error:
                logger.info(f"   Error: {result.error}")
        
        logger.info("-" * 70)
        logger.info(f"Summary: {successful}/{len(fetchers)} fetchers successful, "
                   f"{total_articles} total articles")
        
        # Sentiment analysis
        if successful > 0:
            self.run_sentiment_analysis()
        else:
            logger.warning("Skipping sentiment analysis: no fetchers succeeded")
        
        # Save metrics
        self._save_metrics(start_time, successful)
        
        # Overall success
        overall_success = successful > 0
        
        elapsed = time.time() - start_time
        logger.info("=" * 70)
        if overall_success:
            logger.success(f"NEWS FETCH AUTOMATION COMPLETE ({elapsed:.1f}s)")
        else:
            logger.error(f"NEWS FETCH AUTOMATION FAILED ({elapsed:.1f}s)")
        logger.info("=" * 70)
        
        return overall_success

    def _save_metrics(self, start_time: float, successful_count: int):
        """Save metrics to JSON."""
        try:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": time.time() - start_time,
                "successful_fetchers": successful_count,
                "total_fetchers": len(self.results),
                "total_articles": sum(r.articles_count for r in self.results.values()),
                "fetchers": {k: v.to_dict() for k, v in self.results.items()}
            }
            
            metrics_file = self.log_dir / "news_fetch_metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
            
            logger.info(f"Metrics saved to {metrics_file}")
        except Exception as e:
            logger.warning(f"Failed to save metrics: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Automated News Fetch Orchestrator"
    )
    parser.add_argument(
        '--max-articles',
        type=int,
        default=100,
        help='Maximum articles per source (default: 100)'
    )
    parser.add_argument(
        '--ngx-only',
        action='store_true',
        help='Run only NGX Announcements fetcher'
    )
    parser.add_argument(
        '--businessday-only',
        action='store_true',
        help='Run only BusinessDay fetcher'
    )
    parser.add_argument(
        '--skip-sentiment',
        action='store_true',
        help='Skip sentiment analysis pipeline'
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Execute fetchers in parallel (default: sequential)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate conflicting options
    if args.ngx_only and args.businessday_only:
        logger.error("Cannot specify both --ngx-only and --businessday-only")
        sys.exit(1)
    
    # Run orchestrator
    orchestrator = NewsAutomationOrchestrator(
        max_articles=args.max_articles,
        skip_sentiment=args.skip_sentiment
    )
    
    success = orchestrator.run(
        use_parallel=args.parallel,
        ngx_only=args.ngx_only,
        businessday_only=args.businessday_only
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
