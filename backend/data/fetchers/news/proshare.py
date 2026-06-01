"""
Fetcher for Proshare Nigeria articles.

PRIORITY 2 — investor-focused analysis; complements Nairametrics with deeper
financial commentary. Tackle this after Nairametrics + NGX announcements +
BusinessDay are working.

STATUS: not yet implemented.
ASSIGNED TO: (news teammate)
SPEC: see data/fetchers/news/README.md for the schema contract.
REFERENCE: data/fetchers/broadstreet.py shows the full pattern.

TODO:
  1. Read https://proshareng.com/robots.txt
  2. Identify the markets / company-news section
  3. Implement fetch_articles() returning a DataFrame matching ARTICLE_COLUMNS
  4. Cache raw HTML to data/output/raw/news/proshare/
"""
from .base import NewsFetcherBase


class ProshareFetcher(NewsFetcherBase):

    SOURCE_ID = "proshare"
    BASE_URL = "https://proshareng.com"

    def fetch_articles(self, since_date=None, max_articles=None):
        # TODO: implement
        raise NotImplementedError("ProshareFetcher.fetch_articles is not implemented yet")
