import os
import random
import time
from pathlib import Path

import pandas as pd
import requests
import urllib3.exceptions

from io import StringIO
from bs4 import BeautifulSoup
# pyrefly: ignore [missing-import]
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from data.config import (
    BASE_URL,
    LOGIN_ENDPOINT,
    BROADSTREET_USERNAME,
    BROADSTREET_PASSWORD,
    USER_AGENT,
    FROM_EMAIL,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    REQUEST_TIMEOUT,
    RAW_DIR,
    LOG_DIR,
    KILLSWITCH_PATH,
)

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
logger.add(
    f"{LOG_DIR}/broadstreet.log",
    rotation="1 MB",
    level="INFO",
)


class KillSwitchError(Exception):
    """Operator-triggered abort. Touch data/.killswitch to raise."""


class SoftBlockError(Exception):
    """Response looks like a login page, captcha, 403, or empty body."""


class RequestCapExceeded(Exception):
    """The per-run request cap has been hit."""


class BroadStreetFetcher:

    def __init__(self, max_requests=None):

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "From": FROM_EMAIL,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })

        self.max_requests = max_requests
        self.request_count = 0

    # -------- safety scaffolding --------

    def _check_killswitch(self):

        if os.path.exists(KILLSWITCH_PATH):
            raise KillSwitchError(
                f"Killswitch file present at {KILLSWITCH_PATH}. Aborting."
            )

    def _check_cap(self):

        if self.max_requests is not None and self.request_count >= self.max_requests:
            raise RequestCapExceeded(
                f"Hit per-run cap of {self.max_requests} requests."
            )

    def _polite_sleep(self):

        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)

    def _detect_soft_block(self, response):

        # Logged out — response contains login form
        if 'name="user_name"' in response.text and 'name="user_pass"' in response.text:
            raise SoftBlockError("Response contains login form — session expired.")

        lower = response.text.lower()
        if "captcha" in lower or "are you a human" in lower:
            raise SoftBlockError("Response mentions captcha.")

        if response.status_code in (403, 451):
            raise SoftBlockError(
                f"HTTP {response.status_code} — refusing to continue."
            )

        if len(response.text) < 100:
            raise SoftBlockError(
                f"Response unusually short ({len(response.text)} bytes)."
            )

    @retry(
        retry=retry_if_exception_type((
            requests.HTTPError,
            requests.ConnectionError,
            requests.Timeout,
            requests.exceptions.ChunkedEncodingError,
            urllib3.exceptions.ProtocolError,
            ConnectionResetError,
        )),
        wait=wait_exponential(multiplier=30, min=30, max=120),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _polite_get(self, url, save_raw_to=None):

        self._check_killswitch()
        self._check_cap()
        self._polite_sleep()

        logger.info(f"GET {url}")

        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        self.request_count += 1

        if response.status_code == 429:
            logger.warning("HTTP 429 Too Many Requests — backing off")
            raise requests.HTTPError("429 Too Many Requests", response=response)

        if response.status_code >= 500:
            raise requests.HTTPError(
                f"{response.status_code} {response.reason}",
                response=response,
            )

        self._detect_soft_block(response)

        if save_raw_to:
            Path(save_raw_to).parent.mkdir(parents=True, exist_ok=True)
            Path(save_raw_to).write_text(response.text, encoding="utf-8")

        return response

    # -------- authentication --------

    def login(self):

        logger.info("Attempting BroadStreet login...")

        payload = {
            "user_name": BROADSTREET_USERNAME,
            "user_pass": BROADSTREET_PASSWORD,
            "doLogin": "undefined",
            "login_type": "LA",
        }

        response = self.session.post(
            LOGIN_ENDPOINT,
            data=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise Exception(
                f"Login request failed with status code {response.status_code}"
            )

        cookies = self.session.cookies.get_dict()

        if "PHPSESSID" not in cookies:
            raise Exception(
                "Authentication failed: PHPSESSID cookie not found"
            )

        logger.success("BroadStreet login successful")

    # -------- discovery (Stage 1) --------

    def fetch_sectors(self):

        """
        Return [{sector_id, sector_name}] from /sector.php.
        """

        url = f"{BASE_URL}/sector.php"
        save_to = f"{RAW_DIR}/sectors/_sector_list.html"

        response = self._polite_get(url, save_raw_to=save_to)
        soup = BeautifulSoup(response.text, "lxml")

        sectors = []
        seen = set()

        for a in soup.find_all("a", href=True):

            href = a["href"]

            if "company.php?sId=" not in href:
                continue

            try:
                sid = int(href.split("sId=")[1].split("&")[0])
            except (IndexError, ValueError):
                continue

            if sid in seen:
                continue

            seen.add(sid)
            name = a.get_text(strip=True)

            if name:
                sectors.append({"sector_id": sid, "sector_name": name})

        logger.success(f"Discovered {len(sectors)} sectors")

        return sectors

    def fetch_companies_in_sector(self, sector_id, sector_name):

        """
        Return [{ticker, name, sector, sector_id, detail_url}] from
        /company.php?sId=<sector_id>.

        Handles two URL formats present on BroadStreet:
          - /company-detail/<slug>-summary-<TICKER>/qs  (banking sector only)
          - compDetail.php?s=<TICKER>&p=qs              (all other sectors)
        """

        url = f"{BASE_URL}/company.php?sId={sector_id}"
        save_to = f"{RAW_DIR}/sectors/sector_{sector_id}.html"

        response = self._polite_get(url, save_raw_to=save_to)
        soup = BeautifulSoup(response.text, "lxml")

        # Pass 1: build {ticker: full_name} from the &p=cpr links — those
        # carry the full company name. The &p=qs links only carry the ticker.
        names = {}
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "compDetail.php?s=" in href and "p=cpr" in href:
                ticker = self._extract_ticker_from_query(href)
                full_name = a.get_text(strip=True)
                if ticker and full_name:
                    names[ticker] = full_name

        # Pass 2: collect tickers from &p=qs links (both URL formats).
        companies = []
        seen = set()

        for a in soup.find_all("a", href=True):

            href = a["href"]
            ticker = None

            if "/company-detail/" in href and "-summary-" in href and "/qs" in href:
                try:
                    ticker = href.split("-summary-")[1].split("/qs")[0]
                except IndexError:
                    continue
            elif "compDetail.php?s=" in href and "p=qs" in href:
                ticker = self._extract_ticker_from_query(href)

            if not ticker or ticker in seen:
                continue

            seen.add(ticker)

            name = (
                names.get(ticker)
                or self._derive_name_from_slug(href)
                or a.get_text(strip=True)
                or ticker
            )

            companies.append({
                "ticker": ticker,
                "name": name,
                "sector": sector_name,
                "sector_id": sector_id,
                # Canonical fetch URL — works for all tickers, used by Stage 2/3.
                "detail_url": f"/compDetail.php?s={ticker}&p=qs",
            })

        logger.info(
            f"Sector {sector_id} ({sector_name}): {len(companies)} companies"
        )

        return companies

    @staticmethod
    def _extract_ticker_from_query(href):
        """Pull TICKER out of '...?s=TICKER&p=...' style URLs."""
        try:
            ticker = href.split("s=", 1)[1].split("&", 1)[0]
        except IndexError:
            return None
        return ticker.strip() or None

    @staticmethod
    def _derive_name_from_slug(href):
        """
        For '/company-detail/<slug>-summary-<TICKER>/qs' URLs, derive a
        human name from the slug (e.g. 'access-bank-PLC' -> 'Access Bank PLC').
        Returns None for non-slug URLs.
        """
        if "/company-detail/" not in href or "-summary-" not in href:
            return None
        try:
            slug = href.split("/company-detail/")[1].split("-summary-")[0]
        except IndexError:
            return None
        if not slug:
            return None
        parts = slug.split("-")
        return " ".join(p if p.isupper() else p.capitalize() for p in parts)

    # -------- historical OHLCV (Stage 2) --------

    HIST_COLUMNS = ["date", "pclose", "high", "low", "close", "volume", "change"]

    def fetch_historical_prices(self, ticker, start_year=1991, end_year=None,
                                 max_pages=500, use_cache=True):

        """
        Full historical OHLCV time series for one ticker.

        Returns (df, complete) where:
            df       — DataFrame [date, pclose, high, low, close, volume, change]
            complete — True if pagination ended naturally; False on partial/error

        use_cache=True: re-uses raw HTML already on disk (zero HTTP).
        Critical for resumable backfill and fast recovery.
        """

        import datetime as _dt
        if end_year is None:
            end_year = _dt.date.today().year

        all_rows = []
        seen_dates = set()
        last_error = None

        for page in range(1, max_pages + 1):

            url = (
                f"{BASE_URL}/compDetail.php?"
                f"prcLstHid=1&s={ticker}&p=qhp&prHisType=d"
                f"&strtMonth=01&strtDay=1&strtYear={start_year}"
                f"&endMonth=12&endDay=31&endYear={end_year}"
                f"&page={page}"
            )

            save_to = Path(f"{RAW_DIR}/tickers/{ticker}/qhp_page_{page}.html")

            html = None
            if use_cache and save_to.exists():
                try:
                    html = save_to.read_text(encoding="utf-8")
                    logger.info(f"{ticker}: page {page} from cache")
                except Exception as e:
                    logger.warning(
                        f"{ticker}: cache read failed for page {page} — {e}"
                    )
                    html = None

            if html is None:
                try:
                    response = self._polite_get(url, save_raw_to=str(save_to))
                except (KillSwitchError, SoftBlockError, RequestCapExceeded):
                    raise  # operator-level signals — bubble up
                except Exception as e:
                    logger.error(
                        f"{ticker}: page {page} fetch failed — {e}. "
                        f"Saving partial data ({len(all_rows)} rows so far)."
                    )
                    last_error = e
                    break
                html = response.text

            rows = self._parse_history_table(html)

            if not rows:
                logger.info(f"{ticker}: page {page} empty — end of history")
                break

            # BroadStreet returns the last real page repeatedly when you
            # request pages past the data range. Stop on the first page
            # that contributes zero new dates.
            new_rows = [r for r in rows if r["date"] not in seen_dates]

            if not new_rows:
                logger.info(
                    f"{ticker}: page {page} all-duplicate "
                    f"(server looping last page) — end of history"
                )
                break

            all_rows.extend(new_rows)
            seen_dates.update(r["date"] for r in new_rows)
            logger.info(f"{ticker}: page {page} +{len(new_rows)} rows")

        else:
            # for-else: ran out of pages without breaking
            logger.warning(
                f"{ticker}: hit max_pages={max_pages} without natural end. "
                f"May be incomplete."
            )
            last_error = last_error or RuntimeError(f"max_pages cap ({max_pages})")

        complete = last_error is None

        if not all_rows:
            logger.warning(f"{ticker}: no historical data found")
            return pd.DataFrame(columns=self.HIST_COLUMNS), complete

        df = pd.DataFrame(all_rows)

        df["date"] = pd.to_datetime(
            df["date"], format="%d-%m-%Y", errors="coerce"
        ).dt.date

        for col in ["pclose", "high", "low", "close", "change", "volume"]:
            df[col] = df[col].astype(str).str.replace(",", "", regex=False)

        for col in ["pclose", "high", "low", "close", "change"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")

        df = (
            df.dropna(subset=["date"])
              .sort_values("date")
              .drop_duplicates(subset=["date"])
              .reset_index(drop=True)
        )

        if not df.empty:
            tag = "complete" if complete else "PARTIAL"
            logger.success(
                f"{ticker}: {len(df)} rows ({tag}) "
                f"({df['date'].min()} -> {df['date'].max()})"
            )

        return df, complete

    @staticmethod
    def _parse_history_table(html):

        """
        Extract OHLCV rows from a historical-prices page.
        Returns a list of dicts (strings, not typed yet).
        """

        soup = BeautifulSoup(html, "lxml")
        required = {"date", "pclose", "high", "low", "close", "volume", "change"}

        for table in soup.find_all("table"):

            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            header_cells = [
                td.get_text(strip=True).lower()
                for td in rows[0].find_all(["td", "th"])
            ]

            if not required.issubset(set(header_cells)):
                continue

            col_idx = {h: i for i, h in enumerate(header_cells)}

            data_rows = []

            for tr in rows[1:]:

                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cells) < 7:
                    continue

                date_cell = cells[col_idx["date"]]
                # Filter out pagination row / empty row — dates look like DD-MM-YYYY
                if not date_cell or date_cell.count("-") != 2:
                    continue

                data_rows.append({
                    "date":    date_cell,
                    "pclose":  cells[col_idx["pclose"]],
                    "high":    cells[col_idx["high"]],
                    "low":     cells[col_idx["low"]],
                    "close":   cells[col_idx["close"]],
                    "volume":  cells[col_idx["volume"]],
                    "change":  cells[col_idx["change"]],
                })

            return data_rows

        return []

    # -------- corporate actions (dividends + bonuses) --------

    def fetch_corporate_actions(self, ticker):
        """
        Scrape the BroadStreet Dividend History page (compDetail.php?p=qdh)
        for `ticker` and return RAW corporate-action records.

        Returns a DataFrame with columns:
            ticker         - BroadStreet symbol
            declared_date  - date from the page. NOTE: this is the FISCAL
                             YEAR-END / declaration date, NOT the ex-date.
                             The true ex-date is resolved downstream by
                             reconciling against the price series (piece 2).
            action_type    - 'cash_dividend' (Type=Cash) | 'bonus' (Type=Share)
                             | 'unknown:<type>' for anything else
            raw_value      - the raw Payout string ('8.03', '4 for 1', ...)
            source         - 'broadstreet_qdh'

        Deliberately a faithful, UNVALIDATED extraction: ratio interpretation
        and ex-date resolution happen downstream, so nothing here can corrupt
        adjusted prices. Empty DataFrame if the ticker has no dividend history.
        """
        url = f"{BASE_URL}/compDetail.php?s={ticker}&p=qdh"
        resp = self._polite_get(url)

        try:
            tables = pd.read_html(StringIO(resp.text))
        except ValueError:
            tables = []

        date_pat = r"^\d{1,2}-[A-Za-z]{3}-\d{4}$"
        records = []
        for t in tables:
            if t.shape[1] != 3:
                continue
            t = t.copy()
            t.columns = ["date", "payout", "type"]
            rows = t[t["date"].astype(str).str.match(date_pat, na=False)]
            if rows.empty:
                continue
            for _, r in rows.iterrows():
                typ = str(r["type"]).strip().lower()
                action = {"cash": "cash_dividend", "share": "bonus"}.get(
                    typ, f"unknown:{typ}"
                )
                ts = pd.to_datetime(r["date"], format="%d-%b-%Y", errors="coerce")
                records.append({
                    "ticker": ticker,
                    "declared_date": ts.date() if pd.notna(ts) else None,
                    "action_type": action,
                    "raw_value": str(r["payout"]).strip(),
                    "source": "broadstreet_qdh",
                })
            break  # first matching 3-col table is the dividend history

        df = pd.DataFrame(
            records,
            columns=["ticker", "declared_date", "action_type", "raw_value", "source"],
        )
        n_bonus = int((df["action_type"] == "bonus").sum()) if len(df) else 0
        n_cash = int((df["action_type"] == "cash_dividend").sum()) if len(df) else 0
        logger.info(f"{ticker}: {len(df)} corp-action record(s) "
                    f"({n_bonus} bonus, {n_cash} cash)")
        return df

    # -------- existing helpers (exchange-rate POC) --------

    def fetch_market_page(self, url):

        logger.info(f"Fetching market page: {url}")

        response = self.session.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            raise Exception(f"Failed to fetch page: {url}")

        logger.success("Market page fetched successfully")

        return response.text

    def extract_tables(self, html):

        """
        Optional helper. Useful for debugging and inspecting all tables on page.
        """

        logger.info("Extracting HTML tables")

        try:
            tables = pd.read_html(StringIO(html))

            if len(tables) == 0:
                raise Exception("No tables found on page")

            logger.success(f"{len(tables)} table(s) extracted")

            return tables

        except ValueError as e:
            logger.error(f"Table extraction failed: {str(e)}")
            raise Exception("Failed to extract HTML tables")

    def get_exchange_rate_table(self, html):

        logger.info("Parsing exchange rate table")

        soup = BeautifulSoup(html, "lxml")
        tables = soup.find_all("table")

        for table in tables:

            rows = table.find_all("tr")
            extracted_rows = []

            for row in rows:
                cols = row.find_all("td")
                cols = [col.get_text(strip=True) for col in cols]

                if len(cols) == 10:
                    extracted_rows.append(cols)

            if len(extracted_rows) > 0:

                logger.success(
                    f"Exchange rate table parsed successfully "
                    f"with {len(extracted_rows)} rows"
                )

                columns = [
                    "currency",
                    "last_trade",
                    "ngn",
                    "usd",
                    "jpy",
                    "gbp",
                    "chf",
                    "cad",
                    "zar",
                    "eur",
                ]

                df = pd.DataFrame(extracted_rows, columns=columns)
                return df

        raise Exception("Exchange rate table not found")

    # -------- NSE All-Share Index snapshot (Stage 4) --------

    ASI_URL = "/asiDetail.php?p=apr"

    # Map BroadStreet's label text -> our canonical indicator name.
    # Keys are lower-cased & punctuation-stripped for robust matching.
    _ASI_LABEL_MAP = {
        "current index value":  "nse_asi_close",
        "previous day value":   "nse_asi_prev_close",
        "open":                 "nse_asi_open",
        "no of deals":          "nse_asi_deals",
        "volume":               "nse_asi_volume",
        "mkt capitalization":   "nse_asi_mkt_cap",
    }

    def fetch_asi_snapshot(self):
        """
        Fetch today's NSE All-Share Index snapshot from /asiDetail.php?p=apr.

        Output: long-format DataFrame matching the macro_indicators schema:
            date         datetime   from "Last Trade Date"
            indicator    str        e.g. "nse_asi_close"
            value        float64    numeric value
            source       str        "broadstreet"
            unit         str        "index_points" / "shares" / "deals" / "NGN"

        Idempotent: re-running on the same trading day produces the same rows
        (dedup happens at save-time on (date, indicator) by the writer).
        """
        import re as _re

        url = f"{BASE_URL}{self.ASI_URL}"
        save_to = f"{RAW_DIR}/asi/snapshot_{self._today_str()}.html"
        response = self._polite_get(url, save_raw_to=save_to)

        soup = BeautifulSoup(response.text, "lxml")

        # Extract every (label, value) pair from any table on the page.
        # The snapshot is split across several small key-value tables;
        # we flatten them into one dict.
        pairs = {}
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                # Look for clean 2-cell key/value rows
                if len(cells) == 2 and cells[0] and cells[1]:
                    key = self._normalize_label(cells[0])
                    if key in self._ASI_LABEL_MAP:
                        pairs[key] = cells[1]
                # Also handle "Change" which appears as "-1,366.90 (-0.54%)"
                if len(cells) == 2 and cells[0].lower().strip().rstrip(":") == "change":
                    pairs["change"] = cells[1]
                # And "Last Trade Date"
                if len(cells) == 2 and cells[0].lower().strip().rstrip(":") == "last trade date":
                    pairs["last_trade_date"] = cells[1]

        if "last_trade_date" not in pairs:
            logger.warning("[asi] no 'Last Trade Date' found on snapshot page")
            return pd.DataFrame(columns=["date", "indicator", "value", "source", "unit"])

        # Parse the trade date (e.g. "15-May-2026")
        try:
            trade_date = pd.to_datetime(pairs["last_trade_date"], format="%d-%b-%Y")
        except (ValueError, TypeError) as e:
            logger.error(f"[asi] could not parse trade date {pairs['last_trade_date']!r}: {e}")
            return pd.DataFrame(columns=["date", "indicator", "value", "source", "unit"])

        rows = []

        # Standard numeric indicators
        for label_key, indicator in self._ASI_LABEL_MAP.items():
            if label_key not in pairs:
                continue
            raw_val = pairs[label_key].replace(",", "").strip()
            try:
                value = float(raw_val)
            except ValueError:
                continue
            unit = self._asi_unit(indicator)
            rows.append({
                "date": trade_date,
                "indicator": indicator,
                "value": value,
                "source": "broadstreet",
                "unit": unit,
            })

        # Parse "change" specially: "-1,366.90 (-0.54%)" → two indicators
        if "change" in pairs:
            change_match = _re.match(r"\s*(-?[\d,.]+)\s*\(\s*(-?[\d.]+)\s*%\s*\)", pairs["change"])
            if change_match:
                try:
                    abs_change = float(change_match.group(1).replace(",", ""))
                    pct_change = float(change_match.group(2))
                    rows.append({
                        "date": trade_date,
                        "indicator": "nse_asi_change",
                        "value": abs_change,
                        "source": "broadstreet",
                        "unit": "index_points",
                    })
                    rows.append({
                        "date": trade_date,
                        "indicator": "nse_asi_change_pct",
                        "value": pct_change,
                        "source": "broadstreet",
                        "unit": "percent",
                    })
                except ValueError:
                    pass

        df = pd.DataFrame(rows)
        if df.empty:
            logger.warning("[asi] snapshot produced no rows")
        else:
            logger.success(
                f"[asi] snapshot {trade_date.date()}: "
                f"{len(df)} indicators, close={df.loc[df['indicator']=='nse_asi_close', 'value'].iloc[0] if 'nse_asi_close' in df['indicator'].values else 'n/a'}"
            )
        return df

    @staticmethod
    def _normalize_label(text):
        """Lower-case, strip trailing colon/whitespace for robust label matching."""
        return text.lower().strip().rstrip(":").strip()

    @staticmethod
    def _asi_unit(indicator):
        if indicator.endswith("deals"):
            return "deals"
        if indicator.endswith("volume"):
            return "shares"
        if indicator.endswith("mkt_cap"):
            return "NGN"
        if indicator.endswith("change_pct"):
            return "percent"
        return "index_points"

    @staticmethod
    def _today_str():
        import datetime as _dt
        return _dt.date.today().isoformat()
