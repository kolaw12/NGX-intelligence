"""
Fetcher for Nairametrics articles.

PRIORITY 1 — start here. Most NGX-focused publication; clear ticker tagging
in many articles makes entity extraction easier later.

STATUS: not yet implemented.
ASSIGNED TO: Tomi
SPEC: see data/fetchers/news/README.md for the schema contract.
REFERENCE: data/fetchers/broadstreet.py shows the full pattern for a
           working fetcher (session, polite_get, parsing, manifest).

TODO:
  1. Read https://nairametrics.com/robots.txt — confirm we're allowed
  2. Find the article-listing pattern (category pages, archive, RSS feed?)
  3. Implement fetch_articles() returning a DataFrame matching ARTICLE_COLUMNS
  4. Cache raw HTML to data/output/raw/news/nairametrics/
  5. Write parquets via self.write_parquet(df, year)
"""
from .base import NewsFetcherBase


class NairametricsFetcher(NewsFetcherBase):

    SOURCE_ID = "nairametrics"
    BASE_URL = "https://nairametrics.com"

    def fetch_articles(self, since_date=None, max_articles=None):
        # TODO: implement
        raise NotImplementedError("NairametricsFetcher.fetch_articles is not implemented yet")
