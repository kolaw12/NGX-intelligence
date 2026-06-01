"""
Fetcher for Central Bank of Nigeria (CBN) exchange rate data.

Pulls NGN exchange rates against all major currencies from CBN's public
JSON API at:
    https://www.cbn.gov.ng/api/GetAllExchangeRates

The API returns the full historical dataset across all currencies in one
response (~8 MB JSON, tens of thousands of rows). No pagination, no auth,
no JavaScript rendering — clean structured data.

API response schema (each record):
    {
        "id":          int,
        "currency":    str,    # "USD", "EURO", "POUNDS STERLING", etc.
        "ratedate":    str,    # "YYYY-MM-DD"
        "buyingrate":  str,    # NGN per unit foreign currency
        "centralrate": str,    # canonical "official rate"
        "sellingrate": str
    }

Our output schema (long-format, matches HANDOFF.md section 11):
    date         datetime64
    indicator    str           e.g. "usd_ngn_rate", "euro_ngn_rate"
    value        float64       NGN per unit of foreign currency (central rate)
    source       str           "cbn"
    unit         str           "NGN/USD", "NGN/EURO", etc.

Usage:
    from data.fetchers.cbn import CBNFetcher
    fetcher = CBNFetcher()
    df = fetcher.fetch_exchange_rates()         # all currencies, all history
    df = fetcher.fetch_exchange_rates(currencies=["USD", "EURO"])
    fetcher.save(df)
"""
import os
import random
import re
import time
from pathlib import Path

import pandas as pd
import requests
import urllib3.exceptions

# pyrefly: ignore [missing-import]
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from data.config import (
    USER_AGENT,
    FROM_EMAIL,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    REQUEST_TIMEOUT,
    LOG_DIR,
    KILLSWITCH_PATH,
    DATA_DIR,
)

# Where macro output lives
MACRO_RAW_DIR = f"{DATA_DIR}/output/raw/macro/cbn"
MACRO_PROCESSED_DIR = f"{DATA_DIR}/output/processed/macro"

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
logger.add(
    f"{LOG_DIR}/cbn.log",
    rotation="1 MB",
    level="INFO",
)


# ---------- exceptions (mirror broadstreet.py pattern) ----------

class KillSwitchError(Exception):
    """Operator-triggered abort. Touch data/.killswitch to raise."""


class SoftBlockError(Exception):
    """Response looks unexpected — 403/451 / empty / not JSON."""


# ---------- the fetcher ----------

class CBNFetcher:

    BASE_URL = "https://www.cbn.gov.ng"
    API_PATH = "/api/GetAllExchangeRates"

    # CBN's currency naming is inconsistent (trailing spaces, singular/plural
    # variants, mixed cases). Normalize to canonical names here. After this
    # map is applied, "US DOLLAR ", "US DOLLAR", "us dollar" all become "US DOLLAR".
    CURRENCY_ALIASES = {
        "POUND STERLING": "POUNDS STERLING",
        "DANISH KRONER":  "DANISH KRONA",
        "YEN":            "JAPANESE YEN",
    }

    # Convenience mapping so callers can pass ISO codes ("USD", "EUR")
    # instead of CBN's quirky names ("US DOLLAR", "EURO").
    ISO_TO_CBN = {
        "USD": "US DOLLAR",
        "EUR": "EURO",
        "GBP": "POUNDS STERLING",
        "JPY": "JAPANESE YEN",
        "CHF": "SWISS FRANC",
        "CNY": "YUAN/RENMINBI",
        "ZAR": "SOUTH AFRICAN RAND",
        "AED": "UAE DIRHAM",
        "DKK": "DANISH KRONA",
        "SAR": "RIYAL",
        "SDR": "SDR",
        "CFA": "CFA",
    }

    # Reference / non-tradeable entries to drop entirely
    CURRENCY_SKIP = {"NAIRA"}

    def __init__(self, max_requests=None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "From": FROM_EMAIL,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.max_requests = max_requests
        self.request_count = 0

    # ---------- safety scaffolding ----------

    def _check_killswitch(self):
        if os.path.exists(KILLSWITCH_PATH):
            raise KillSwitchError(
                f"Killswitch file present at {KILLSWITCH_PATH}. Aborting."
            )

    def _polite_sleep(self):
        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

    def _detect_soft_block(self, response):
        if response.status_code in (403, 451):
            raise SoftBlockError(
                f"HTTP {response.status_code} — refusing to continue."
            )
        if len(response.content) < 100:
            raise SoftBlockError(
                f"Response unusually short ({len(response.content)} bytes)."
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
        self._polite_sleep()

        logger.info(f"[cbn] GET {url}")
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        self.request_count += 1

        if response.status_code == 429:
            logger.warning("[cbn] HTTP 429 — backing off")
            raise requests.HTTPError("429 Too Many Requests", response=response)
        if response.status_code >= 500:
            raise requests.HTTPError(
                f"{response.status_code} {response.reason}",
                response=response,
            )

        self._detect_soft_block(response)

        if save_raw_to:
            Path(save_raw_to).parent.mkdir(parents=True, exist_ok=True)
            Path(save_raw_to).write_bytes(response.content)

        return response

    # ---------- fetching ----------

    def fetch_exchange_rates(self, currencies=None, start_date=None,
                             rate_type="centralrate", save_raw=True):
        """
        Fetch CBN exchange rates via the public JSON API.

        Args:
            currencies:  list of currency names to include (CBN-native names
                         like "USD", "EURO", "POUNDS STERLING"). None = all.
            start_date:  str "YYYY-MM-DD" — drop rows before this date. None = all.
            rate_type:   one of "buyingrate", "centralrate", "sellingrate".
                         "centralrate" is the canonical "official rate".
            save_raw:    if True, save the raw JSON response for debugging.

        Returns:
            DataFrame with columns: date, indicator, value, source, unit
            (long-format, one row per (date, currency) combination)
        """

        if rate_type not in ("buyingrate", "centralrate", "sellingrate"):
            raise ValueError(
                f"rate_type must be one of buyingrate/centralrate/sellingrate, "
                f"got {rate_type!r}"
            )

        url = f"{self.BASE_URL}{self.API_PATH}"
        save_to = f"{MACRO_RAW_DIR}/exchange_rates_api.json" if save_raw else None

        response = self._polite_get(url, save_raw_to=save_to)

        try:
            data = response.json()
        except ValueError as e:
            raise SoftBlockError(f"Response is not valid JSON: {e}")

        if not isinstance(data, list) or not data:
            logger.warning(f"[cbn] API returned empty or unexpected payload")
            return self._empty_frame()

        logger.info(f"[cbn] API returned {len(data):,} raw records")

        raw = pd.DataFrame(data)
        required = {"currency", "ratedate", rate_type}
        missing = required - set(raw.columns)
        if missing:
            raise SoftBlockError(
                f"API response missing expected fields: {missing}. "
                f"Got columns: {list(raw.columns)}"
            )

        # Parse types
        raw["ratedate"] = pd.to_datetime(raw["ratedate"], errors="coerce")
        raw[rate_type] = pd.to_numeric(raw[rate_type], errors="coerce")
        raw = raw.dropna(subset=["ratedate", rate_type, "currency"])

        # Normalize currency names: strip whitespace, uppercase, apply aliases
        raw["currency"] = (
            raw["currency"]
            .str.strip()
            .str.upper()
            .replace(self.CURRENCY_ALIASES)
        )

        # Drop non-tradeable / reference entries (e.g. NAIRA against itself)
        raw = raw[~raw["currency"].isin(self.CURRENCY_SKIP)]

        # Filter — currency. Translate ISO codes (USD, EUR, GBP) to CBN names.
        if currencies:
            wanted = {
                self.ISO_TO_CBN.get(c.upper(), c.upper())
                for c in currencies
            }
            raw = raw[raw["currency"].isin(wanted)]
            if raw.empty:
                available = sorted(set(pd.DataFrame(data)["currency"].str.strip().str.upper()))
                logger.warning(
                    f"[cbn] No rows matched currencies={currencies}. "
                    f"Available: {available}"
                )
                return self._empty_frame()

        # Filter — date
        if start_date:
            raw = raw[raw["ratedate"] >= pd.to_datetime(start_date)]

        # Transform to long format
        df = pd.DataFrame({
            "date": raw["ratedate"],
            "indicator": raw["currency"].apply(self._currency_to_indicator),
            "value": raw[rate_type].astype(float),
            "source": "cbn",
            "unit": "NGN/" + raw["currency"].apply(self._normalize_currency_for_unit),
        })

        df = df.sort_values(["indicator", "date"]).reset_index(drop=True)

        logger.success(
            f"[cbn] Returned {len(df):,} rows across "
            f"{df['indicator'].nunique()} indicators "
            f"({df['date'].min().date()} -> {df['date'].max().date()})"
        )
        return df

    # ---------- helpers ----------

    @staticmethod
    def _currency_to_indicator(currency):
        """
        Convert CBN currency name to a machine-readable indicator key.
        e.g. "POUNDS STERLING" -> "pounds_sterling_ngn_rate"
             "YUAN/RENMINBI"   -> "yuan_renminbi_ngn_rate"
             "USD"             -> "usd_ngn_rate"
             "EURO"            -> "euro_ngn_rate"
        """
        slug = re.sub(r"[^a-z0-9]+", "_", currency.lower()).strip("_")
        return f"{slug}_ngn_rate"

    @staticmethod
    def _normalize_currency_for_unit(currency):
        """
        Used in the 'unit' column to keep it readable: replace '/' with '_'.
        e.g. "YUAN/RENMINBI" -> "YUAN_RENMINBI" so unit is "NGN/YUAN_RENMINBI"
        """
        return currency.replace("/", "_").replace(" ", "_")

    @staticmethod
    def _empty_frame():
        return pd.DataFrame(columns=["date", "indicator", "value", "source", "unit"])

    # ---------- output ----------

    def save(self, df, filename="cbn_exchange_rates.parquet"):
        """
        Persist a DataFrame to the macro processed directory.

        Append-and-dedupe semantics: loads any existing version of the file,
        concatenates, drops duplicates on (date, indicator), and rewrites.
        """
        if df.empty:
            logger.warning("[cbn] save() called with empty DataFrame — skipping")
            return

        required = ["date", "indicator", "value", "source", "unit"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        out_dir = Path(MACRO_PROCESSED_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        if out_path.exists():
            existing = pd.read_parquet(out_path)
            existing["date"] = pd.to_datetime(existing["date"])
            combined = pd.concat([existing, df], ignore_index=True)
        else:
            combined = df

        combined = (
            combined
            .drop_duplicates(subset=["date", "indicator"], keep="last")
            .sort_values(["indicator", "date"])
            .reset_index(drop=True)
        )

        combined.to_parquet(out_path, index=False)
        logger.success(
            f"[cbn] Wrote {len(combined):,} rows to {out_path} "
            f"({len(df)} new this run)"
        )
        return out_path
