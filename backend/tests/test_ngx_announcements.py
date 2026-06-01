"""
Tests for data/fetchers/news/ngx_announcements.py

Covers the parts that are VERIFIED offline:
  - TickerMatcher: correct hits, false-positive resistance, exclude set
  - _parse_announcement: skips body-less pages, parses a well-formed one,
    produces the exact ARTICLE_COLUMNS contract with tz-aware dates

These tests need NO network. They use the real data/master/tickers.csv
in the repo for the matcher, and a small inline HTML fixture for parsing.

Run:  pytest tests/test_ngx_announcements.py -v
"""

import datetime as _dt

import pytest

from data.fetchers.news.base import ARTICLE_COLUMNS
from data.fetchers.news.ngx_announcements import (
    TickerMatcher,
    NGXAnnouncementsFetcher,
)


# --------------------------------------------------------------------------- #
#  TickerMatcher                                                              #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def matcher():
    # Uses the real repo registry at data/master/tickers.csv
    return TickerMatcher()


@pytest.fixture(scope="module")
def ngx_matcher():
    # As the NGX fetcher builds it: exchange excluded from self-tagging
    return TickerMatcher(exclude={"NGX"})


def test_matches_company_name(matcher):
    got = matcher.find(
        "Dangote Cement PLC notifies the Exchange of its audited results."
    )
    assert "DCE" in got


def test_name_does_not_bleed_between_related_companies(matcher):
    # 'Dangote Cement' must not also pull Dangote Sugar / Flour
    got = matcher.find("Dangote Cement PLC recommends a final dividend.")
    assert "DCE" in got
    assert "DSR" not in got and "DFM" not in got


def test_matches_bare_ticker_token(matcher):
    got = matcher.find("ZEN has filed its Q3 results with the regulator.")
    assert "ZEN" in got


def test_multi_company(matcher):
    got = matcher.find(
        "Zenith Bank PLC and BUA Cement and Okomu Oil Palm PLC advanced."
    )
    for t in ("ZEN", "BUA", "OKM"):
        assert t in got
    # BUA Cement, not BUA Foods
    assert "BUF" not in got


def test_stopword_tokens_not_matched(matcher):
    got = matcher.find("THE BOARD AND THE CEO CONFIRMED ALL FOR THE FY AGM.")
    assert got == []


def test_substring_not_matched(matcher):
    # 'ABC' must not match inside an ordinary word
    got = matcher.find("An alphabetical abcdef sequence, nothing listed here.")
    assert "ABC" not in got


def test_empty_input_returns_empty_list(matcher):
    assert matcher.find("") == []
    assert matcher.find(None) == []
    assert matcher.find("", None) == []


def test_result_is_sorted_and_unique(matcher):
    got = matcher.find("Zenith Bank PLC. Zenith Bank PLC again. BUA Cement.")
    assert got == sorted(got)
    assert len(got) == len(set(got))


def test_exclude_suppresses_exchange_self_tag(ngx_matcher):
    # Every NGX filing mentions 'the Nigerian Exchange'; NGX must not be
    # auto-tagged on a filing that is actually about another company.
    got = ngx_matcher.find(
        "Dangote Cement PLC notifies the Nigerian Exchange of its results."
    )
    assert "DCE" in got
    assert "NGX" not in got


def test_default_matcher_still_tags_ngx_when_not_excluded(matcher):
    got = matcher.find("Nigerian Exchange Group PLC released its H1 results.")
    assert "NGX" in got


def test_common_word_does_not_trigger_single_word_company(matcher):
    # "total market capitalisation" must NOT tag Total Nigeria PLC (TNL);
    # single-word distinctive names are matched via ticker only.
    got = matcher.find(
        "Total market capitalisation rose to N160tn at the close of trade."
    )
    assert "TNL" not in got


def test_multiword_company_name_still_matches(matcher):
    got = matcher.find("FTN Cocoa Processors led the gainers today.")
    assert "FTN" in got


# --------------------------------------------------------------------------- #
#  _parse_announcement                                                        #
# --------------------------------------------------------------------------- #

GOOD_HTML = """
<html><head>
<meta property="og:title" content="Zenith Bank PLC - Audited FY Results - NGX"/>
<meta property="article:published_time" content="2026-05-10T09:00:00+00:00"/>
<link rel="canonical" href="https://ngxgroup.com/issuers/news/zenith-fy/?x=1"/>
</head><body>
<article>
<h1>Zenith Bank PLC - Audited FY Results</h1>
<div class="entry-content">
<p>Zenith Bank PLC has submitted its audited financial statements for the
year ended December 31, 2025 to the Nigerian Exchange.</p>
<p>The Board recommends a final dividend, bringing total payout for the
year in line with the bank's stated policy, subject to shareholder
approval at the forthcoming annual general meeting.</p>
</div>
</article>
</body></html>
"""

BODYLESS_HTML = """
<html><head><title>Some announcement - NGX</title>
<meta property="og:title" content="Some announcement"/></head>
<body><article><h1>Some announcement</h1></article></body></html>
"""


def test_parse_good_announcement_matches_contract():
    rec = NGXAnnouncementsFetcher._parse_announcement(
        GOOD_HTML,
        "https://ngxgroup.com/issuers/news/zenith-fy/?x=1",
        TickerMatcher(exclude={"NGX"}),
    )
    assert rec is not None
    assert set(rec.keys()) == set(ARTICLE_COLUMNS)
    assert rec["source"] == "ngx_announcements"
    assert rec["headline"] == "Zenith Bank PLC - Audited FY Results"
    # canonical link used, query stripped
    assert rec["url"] == "https://ngxgroup.com/issuers/news/zenith-fy/"
    # tz-aware, converted to Africa/Lagos (UTC+0 -> +01:00)
    assert rec["published_date"].utcoffset() == _dt.timedelta(hours=1)
    assert rec["published_date"].isoformat() == "2026-05-10T10:00:00+01:00"
    # body present, no HTML leakage
    assert "Zenith Bank PLC has submitted" in rec["article_text"]
    assert "<" not in rec["article_text"]
    # ticker matched from subject; exchange self-tag suppressed
    assert "ZEN" in rec["mentioned_tickers"]
    assert "NGX" not in rec["mentioned_tickers"]


def test_parse_bodyless_is_skipped():
    rec = NGXAnnouncementsFetcher._parse_announcement(
        BODYLESS_HTML,
        "https://ngxgroup.com/issuers/news/empty/",
        TickerMatcher(exclude={"NGX"}),
    )
    assert rec is None  # never emit empty rows (handbook Section 2)


def test_build_dataframe_schema_and_dtypes():
    rec = NGXAnnouncementsFetcher._parse_announcement(
        GOOD_HTML,
        "https://ngxgroup.com/issuers/news/zenith-fy/",
        TickerMatcher(exclude={"NGX"}),
    )
    df = NGXAnnouncementsFetcher._build_dataframe([rec])
    assert list(df.columns) == ARTICLE_COLUMNS
    assert str(df["published_date"].dtype).startswith("datetime64")
    assert df["source"].dtype == "string"
    assert isinstance(df.iloc[0]["mentioned_tickers"], list)