# Automated News Fetch System

Complete automation guide for BusinessDay and NGX Announcements news fetching with sentiment analysis integration.

## Overview

This system provides **production-ready automation** for:
- **NGX Announcements** - Official exchange filings (Priority 1)
- **BusinessDay Nigeria** - Major business daily coverage (Priority 1)
- **Sentiment Analysis** - FinBERT-based sentiment scoring
- **Comprehensive Monitoring** - Logs, metrics, error handling

## Quick Start

### Local Execution

```bash
# Run all fetchers (sequential, default)
python scripts/automate_news_fetch.py

# Run with custom settings
python scripts/automate_news_fetch.py --max-articles 50 --parallel

# Run individual fetchers
python scripts/automate_news_fetch.py --ngx-only
python scripts/automate_news_fetch.py --businessday-only

# Skip sentiment analysis
python scripts/automate_news_fetch.py --skip-sentiment

# Enable verbose logging
python scripts/automate_news_fetch.py --verbose
```

### GitHub Actions Workflow

The workflow is **automatically triggered** at three market times:

| Time | UTC | Description |
|------|-----|-------------|
| **8:55 AM** | 7:55 AM | Before market open |
| **1:00 PM** | 12:00 PM | Mid-trading |
| **4:30 PM** | 3:30 PM | After market close |

**Manual Trigger:**
1. Go to **Actions** → **Daily News Fetch**
2. Click **Run workflow**
3. Configure options:
   - Max articles per source
   - Enable/disable NGX fetcher
   - Enable/disable BusinessDay fetcher
   - Enable/disable sentiment analysis

## Architecture

### Execution Flow

```
┌─────────────────────────────────────────────────────────┐
│       AUTOMATED NEWS FETCH ORCHESTRATOR                │
└─────────────────────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
    ┌───▼────┐              ┌──────▼────┐
    │   NGX  │              │ BusinessDay│
    │Announce│              │  Nigeria   │
    │ments   │              │            │
    └────────┘              └───────────┘
        │                           │
        └─────────────┬─────────────┘
                      │
            ┌─────────▼────────┐
            │ Sentiment Pipeline│
            │   (FinBERT)      │
            └──────────────────┘
                      │
            ┌─────────▼──────────────┐
            │ Warehouse Write & Export│
            └───────────────────────┘
```

### Sequential vs Parallel Execution

**Sequential (Default)** - Safe, predictable
```bash
python scripts/automate_news_fetch.py
```
- NGX Announcements: 3-5 minutes
- BusinessDay: 3-5 minutes
- Sentiment: 5-10 minutes
- **Total: ~15-20 minutes**

**Parallel** - Faster for independent fetchers
```bash
python scripts/automate_news_fetch.py --parallel
```
- NGX + BusinessDay: ~5 minutes (concurrent)
- Sentiment: 5-10 minutes
- **Total: ~10-15 minutes**

## Configuration

### Global Settings

Edit `data/config/news_automation.yaml`:

```yaml
# Max articles per run
MAX_ARTICLES_PER_SOURCE: 100

# Enable individual fetchers
FETCHERS:
  ngx_announcements:
    enabled: true
    max_requests: 200
    timeout_seconds: 300
    
  businessday:
    enabled: true
    max_requests: 200
    timeout_seconds: 300

# Sentiment analysis
SENTIMENT:
  enabled: true
  pipeline_type: "finbert"
```

### Environment Variables

Set these for runtime control:

```bash
# Control article limits
export NEWS_MAX_ARTICLES=50

# Disable FinBERT if needed
export NUPAT_DISABLE_FINBERT=1

# Enable debug logging
export PYTHONUNBUFFERED=1
```

## Fetcher Details

### NGX Announcements

**Source**: https://ngxgroup.com/media-center/news/

**Features**:
- ✓ Official company announcements
- ✓ Ticker matching (conservative, NER-ready)
- ✓ High-priority financial disclosures
- ✓ Real HTML parsing (verified)

**Configuration**:
```yaml
source: "NGX Announcements"
priority: 1
discovery: "/media-center/news/ (pagination)"
parse_method: "static HTML + BeautifulSoup"
ticker_matching: "TickerMatcher class (Section 8)"
```

**Entry Point**:
```python
from data.fetchers.news.ngx_announcements import NGXAnnouncementsFetcher

fetcher = NGXAnnouncementsFetcher(max_requests=200)
articles = fetcher.fetch_articles(max_articles=100)
```

### BusinessDay Nigeria

**Source**: https://businessday.ng/

**Features**:
- ✓ Major business daily
- ✓ Broad NGX company coverage
- ✓ Banking, energy, regulation focus
- ✓ Sitemap-based discovery (robots.txt compliant)

**Configuration**:
```yaml
source: "BusinessDay Nigeria"
priority: 1
discovery: "Yoast news-sitemap.xml"
parse_method: "static HTML + BeautifulSoup"
paywall_handling: "SKIP (PRO articles skipped by default)"
```

**Entry Point**:
```python
from data.fetchers.news.businessday import BusinessDayFetcher

fetcher = BusinessDayFetcher(max_requests=200)
articles = fetcher.fetch_articles(max_articles=100)
```

## Sentiment Analysis

### FinBERT Pipeline

Located in `backend/app/nlp/sentiment_pipeline.py`

**Features**:
- Financial BERT model fine-tuned for sentiment
- Batch processing for efficiency
- Ticker mapping & tagging
- Summary aggregation

**Entry Point**:
```python
from backend.app.nlp.sentiment_pipeline import run_pipeline

run_pipeline(since_days_ago=1)  # Last 24 hours
```

### Daily Sentiment Summary

Automatically computed after news ingestion:
- Per-ticker sentiment scores
- Volume-weighted sentiment
- Hourly aggregations
- Warehouse export

## Monitoring & Logging

### Log Files

```
data/logs/
├── news_fetch_automation.log      # Main execution log
├── news_fetch_metrics.json        # Performance metrics
├── news_fetch_debug.log           # Debug-level details
└── news.log                       # Pipeline stage logs
```

### Metrics Output

`data/logs/news_fetch_metrics.json`:

```json
{
  "timestamp": "2026-06-09T14:30:45.123456",
  "duration_seconds": 145.3,
  "successful_fetchers": 2,
  "total_fetchers": 2,
  "total_articles": 47,
  "fetchers": {
    "NGX Announcements": {
      "source": "NGX Announcements",
      "success": true,
      "articles_count": 12,
      "duration_seconds": 45.2,
      "error": null
    },
    "BusinessDay Nigeria": {
      "source": "BusinessDay Nigeria",
      "success": true,
      "articles_count": 35,
      "duration_seconds": 52.8,
      "error": null
    }
  }
}
```

### Sample Log Output

```
2026-06-09 14:30:01 | INFO     | root | ======================================================================
2026-06-09 14:30:01 | INFO     | root | NEWS FETCH AUTOMATION STARTED
2026-06-09 14:30:01 | INFO     | root | Max articles per source: 100
2026-06-09 14:30:01 | INFO     | root | Parallel execution: False
2026-06-09 14:30:01 | INFO     | root | ======================================================================
2026-06-09 14:30:01 | INFO     | root | Running 2 fetchers sequentially...
2026-06-09 14:30:01 | INFO     | root | Starting NGX Announcements fetcher...
2026-06-09 14:30:46 | INFO     | root | ✓ NGX Announcements: 12 articles in 45.2s
2026-06-09 14:30:47 | INFO     | root | Starting BusinessDay Nigeria fetcher...
2026-06-09 14:31:39 | INFO     | root | ✓ BusinessDay Nigeria: 35 articles in 52.8s
2026-06-09 14:31:39 | INFO     | root | 
2026-06-09 14:31:39 | INFO     | root | FETCHING SUMMARY
2026-06-09 14:31:39 | INFO     | root | ======================================================================
2026-06-09 14:31:39 | INFO     | root | ✓ NGX Announcements: 12 articles | 45.2s
2026-06-09 14:31:39 | INFO     | root | ✓ BusinessDay Nigeria: 35 articles | 52.8s
2026-06-09 14:31:39 | INFO     | root | ======================================================================
2026-06-09 14:31:39 | INFO     | root | Summary: 2/2 fetchers successful, 47 total articles
2026-06-09 14:31:39 | INFO     | root | Starting sentiment analysis pipeline...
2026-06-09 14:42:15 | INFO     | root | ✓ Sentiment pipeline complete in 635.2s
2026-06-09 14:42:15 | INFO     | root | ======================================================================
2026-06-09 14:42:15 | INFO     | root | NEWS FETCH AUTOMATION COMPLETE (780.5s)
2026-06-09 14:42:15 | INFO     | root | ======================================================================
```

## Error Handling

### Soft Errors (Non-fatal)

These are logged as warnings and execution continues:

- Single article parse failure
- Temporary network timeout (with retry)
- Partial data corruption
- Missing optional fields

**Behavior**: Fetcher continues, reports partial results

### Hard Errors (Fatal)

These abort the current fetcher:

- HTTP 403/451 (soft block)
- Captcha detection
- KillSwitch triggered
- Request cap exceeded

**Behavior**: Fetcher stops, logs error, continues to next source

### Retry Logic

**Strategy**: Exponential backoff

```
Attempt 1: immediate
Attempt 2: wait 2 seconds
Attempt 3: wait 4 seconds
Attempt 4: wait 8 seconds
Max delay: 60 seconds
```

## GitHub Actions Workflow

### File: `.github/workflows/daily-news-fetch.yml`

**Triggers**:
- ✓ Schedule (3 times daily)
- ✓ Manual dispatch with input parameters
- ✓ Configurable max articles
- ✓ Per-fetcher enable/disable

**Steps**:
1. Checkout code
2. Set up Python 3.11
3. Install dependencies
4. Fetch NGX (parallel-safe)
5. Fetch BusinessDay (parallel-safe)
6. Run unified news pipeline
7. Build sentiment summary
8. Run FinBERT pipeline
9. Collect logs
10. Upload artifacts
11. Generate report

**Inputs** (Manual Trigger):
```yaml
max_articles:      # Default: 100
run_businessday:   # Default: true
run_ngx:           # Default: true
run_sentiment:     # Default: true
```

### Artifact Output

Downloaded as: `news-fetch-logs-3.11`

```
news-logs/
├── news.log            # News fetching logs
└── sentiment.log       # Sentiment analysis logs
```

### Job Summary

Automatically posted to workflow run:
- Timestamp
- Configuration used
- Status (SUCCESS/PARTIAL)
- Duration
- Article counts per source

## Integration Points

### With Pipeline System

The automation integrates with `data/pipeline.py`:

```bash
# Direct integration
python -m data.pipeline news

# With sentiment summary
python -m data.pipeline sentiment-summary

# Entire workflow
python -m data.pipeline news && python -m data.pipeline sentiment-summary
```

### With Warehouse

Articles are automatically written to:
- `warehouse.articles` table
- `warehouse.article_sentiment` table
- `warehouse.daily_sentiment_summary` table

### With FinBERT

Sentiment pipeline is triggered automatically:
- Analyzes last 24 hours of articles
- Generates per-ticker sentiment
- Exports to warehouse
- Can be disabled with `NUPAT_DISABLE_FINBERT=1`

## Troubleshooting

### No Articles Fetched

**Check**:
1. Are fetchers enabled in config?
2. Review `data/logs/news_fetch_automation.log`
3. Test individual fetcher:
   ```bash
   python scripts/automate_news_fetch.py --ngx-only --verbose
   ```
4. Check if sites are accessible:
   ```bash
   curl -I https://ngxgroup.com/media-center/news/
   curl -I https://businessday.ng/
   ```

### Sentiment Pipeline Timeout

**Solutions**:
1. Skip sentiment: `--skip-sentiment`
2. Increase timeout in workflow
3. Check GPU availability (if using CUDA)
4. Run parallel execution to hide sentiment time

### Rate Limiting / Soft Block

**Handling**:
- Automatic retry with exponential backoff
- Check `SOFT_BLOCK` in logs
- May need to contact site operators
- Respect `robots.txt` and politeness delays

### Memory Issues

**Solutions**:
1. Reduce `--max-articles`
2. Disable parallel execution
3. Increase server RAM
4. Run during off-peak hours

## Advanced Usage

### Custom Metrics Export

```python
from scripts.automate_news_fetch import NewsAutomationOrchestrator

orchestrator = NewsAutomationOrchestrator(max_articles=100)
orchestrator.run(use_parallel=False)

# Access results
for source, result in orchestrator.results.items():
    print(f"{source}: {result.articles_count} articles")
```

### Programmatic Execution

```python
from data.fetchers.news.ngx_announcements import NGXAnnouncementsFetcher
from data.fetchers.news.businessday import BusinessDayFetcher

# NGX
ngx = NGXAnnouncementsFetcher(max_requests=200)
ngx_articles = ngx.fetch_articles(max_articles=100)

# BusinessDay
bd = BusinessDayFetcher(max_requests=200)
bd_articles = bd.fetch_articles(max_articles=100)

# Combine
all_articles = pd.concat([ngx_articles, bd_articles], ignore_index=True)
```

### Scheduled Local Execution

Use system cron to run locally:

```bash
# Run at 8:55 AM, 1:00 PM, 4:30 PM daily
55 7 * * * cd /path/to/project && python scripts/automate_news_fetch.py --max-articles 100
0 12 * * * cd /path/to/project && python scripts/automate_news_fetch.py --max-articles 100
30 15 * * * cd /path/to/project && python scripts/automate_news_fetch.py --max-articles 100
```

## Performance Benchmarks

Typical execution times on GitHub Actions (ubuntu-latest):

| Component | Duration | Notes |
|-----------|----------|-------|
| NGX Announcements | 45-60s | Depends on pagination depth |
| BusinessDay Nigeria | 50-70s | Depends on sitemap size |
| Sentiment Analysis | 300-600s | Depends on article count & GPU |
| **Sequential Total** | 15-20m | NGX + BD + Sentiment |
| **Parallel Total** | 10-15m | NGX & BD concurrent + Sentiment |

## Best Practices

1. **Use Sequential by Default** - More reliable, easier to debug
2. **Monitor Logs Regularly** - Check `data/logs/news_fetch_metrics.json`
3. **Test Before Production** - Manual trigger with `--verbose`
4. **Set Reasonable Timeouts** - Prevent runaway processes
5. **Archive Old Logs** - Keep system clean
6. **Alert on Failures** - Configure Slack/email if needed
7. **Regular Backups** - Preserve article data

## Future Enhancements

- [ ] Real-time WebSocket subscriptions
- [ ] Slack notifications for major news
- [ ] Advanced NER for better ticker matching
- [ ] Custom sentiment models per sector
- [ ] A/B testing different fetcher strategies
- [ ] Distributed execution across workers
- [ ] Advanced caching with Redis
- [ ] GraphQL API for metrics

## Support & Documentation

- **Fetcher Details**: See `data/fetchers/news/` docstrings
- **Pipeline Stages**: See `data/pipeline.py` Stage 6
- **Sentiment Code**: See `backend/app/nlp/sentiment_pipeline.py`
- **Handbook**: Check `data/HANDBOOK.md` (if available)

---

**Last Updated**: 2026-06-09  
**Maintainer**: AI Stock Broker Team
