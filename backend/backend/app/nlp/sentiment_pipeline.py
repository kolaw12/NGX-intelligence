# ── Imports ──────────────────────────────────────
import re
import json
import os
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path
from transformers import pipeline

# ── Import the fetchers directly ─────────────────
# Because we're in the same project now,
# we can import them properly
# from data.fetchers.news.businessday import BusinessDayFetcher
# from data.fetchers.news.ngx_announcements import NGXAnnouncementsFetcher
# from data.fetchers.cbn import CBNFetcher

# try:
#     from data.fetchers.news.nairametrics import NairametricsFetcher
# except NotImplementedError:
#     NairametricsFetcher = None

# ── Sentiment Analysis Pipeline ─────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TICKERS_CSV_CANDIDATES = [
    PROJECT_ROOT / "data" / "master" / "tickers.csv",
    PROJECT_ROOT / "backend" / "data" / "master" / "tickers.csv",
]

# ============================================
# STEP 2 — BROADSTREET MASTER TICKER DICTIONARY
# Maps every variation of a company name 
# to its exact BroadStreet 3-letter symbol
# ============================================

BROADSTREET_TICKERS = {

    # --- BANKING ---
    "zenith bank": "ZEN",
    "zenith": "ZEN",
    "guaranty trust": "GTB",
    "gtco": "GTB",
    "gt bank": "GTB",
    "gtbank": "GTB",
    "access holdings": "ABL",
    "access bank": "ABL",
    "access": "ABL",
    "uba": "UBA",
    "united bank for africa": "UBA",
    "united bank": "UBA",
    "fbn holdings": "FBN",
    "fbn": "FBN",
    "first bank": "FBN",
    "first holdings": "FBN",
    "fcmb group": "FCM",
    "fcmb": "FCM",
    "fidelity bank": "FID",
    "fidelity": "FID",
    "sterling financial": "STL",
    "sterling bank": "STL",
    "sterling": "STL",
    "jaiz bank": "JAB",
    "jaiz": "JAB",
    "vfd group": "VFD",
    "vfd": "VFD",
    "tatum bank": "TAT",
    "tatum": "TAT",

    # --- INSURANCE ---
    "lasaco assurance": "LAS",
    "lasaco": "LAS",
    "linkage assurance": "LAL",
    "linkage": "LAL",
    "veritas kapital": "UNA",
    "veritas": "UNA",
    "fortis global insurance": "SAI",
    "fortis": "SAI",

    # --- TELECOMS ---
    "mtn nigeria": "MTN",
    "mtn": "MTN",
    "airtel africa": "AIRTEL",
    "airtel": "AIRTEL",

    # --- CEMENT & CONSTRUCTION ---
    "dangote cement": "DANGCEM",
    "dangote": "DANGCEM",
    "bua cement": "BUA",
    "bua": "BUA",
    "lafarge": "WAPCO",
    "wapco": "WAPCO",
    "julius berger": "JBERGER",
    "julius": "JBERGER",

    # --- FMCG & CONSUMER GOODS ---
    "nestle nigeria": "NESTLE",
    "nestle": "NESTLE",
    "unilever nigeria": "UNILEVER",
    "unilever": "UNILEVER",
    "nigerian breweries": "NB",
    "nb plc": "NB",
    "guinness nigeria": "GUINNESS",
    "guinness": "GUINNESS",
    "cadbury nigeria": "CADBURY",
    "cadbury": "CADBURY",
    "flour mills": "FLOURMILL",
    "tantalizer": "TNZ",

    # --- OIL & GAS ---
    "seplat energy": "SEPLAT",
    "seplat": "SEPLAT",
    "total nigeria": "TOTAL",
    "total energies nigeria": "TOTAL",
    "conoil": "CONOIL",
    "oando": "OANDO",
    "ardova": "ARDOVA",

    # --- REAL ESTATE ---
    "updc real estate": "UPT",
    "updc property": "UAP",
    "updc": "UPT",

    # --- AGRICULTURE ---
    "ellah lakes": "ELL",
    "japaul gold": "JAO",
    "japaul": "JAO",
    "ftn cocoa": "FTN",
    "ftn": "FTN",

    # --- TECHNOLOGY ---
    "chams holding": "CHM",
    "chams": "CHM",
    "secure electronic": "NSL",
    "etranzact": "ETR",

    # --- ADDITIONAL BANKING & FINANCIAL SERVICES ---
    "stanbic ibtc": "STB",
    "stanbic": "STB",
    "stanbic ibtc holdings": "STB",
    "union bank": "UBN",
    "wema bank": "WEM",
    "wema": "WEM",
    "unity bank": "UNI",
    "unity": "UNI",
    "ecobank": "ECO",
    "eco bank": "ECO",
    "etii": "ECO",
    "providus": "PVD",
    "bank phb": "PHB",
    "skye bank": "SKY",
    "afribank": "AFB",
    "diamond bank": "DIA",
    "intercontinental bank": "ICB",
    "oceanic bank": "OCB",
    "npf microfinance": "NPF",
    "npf microfinance bank": "NPF",
    "united capital": "UBC",
    "africa prudential": "APR",
    "ngx group": "NGX",
    "nigerian exchange group": "NGX",
    "the exchange": "NGX",
    "chapel hill denham": "UTNDI",
    "lotus halal": "UTLOT",
    "meristem growth": "UTMGF",
    "meristem value": "UTMVF",
    "stanbic etf": "UTSTB",
    "vetiva banking": "UTVBF",
    "vetiva consumer": "UTVCF",
    "vetiva griffin": "UTVGF",
    "vetiva industrial": "UTVIF",
    "vetiva s&p": "UTVSF",
    "vetiva sovereign bond": "UTVSF",

    # --- INSURANCE & INVESTMENT HOLDINGS ---
    "aiico": "AIC",
    "aiico insurance": "AIC",
    "axa mansard": "GTA",
    "mansard": "GTA",
    "cornerstone insurance": "CNR",
    "cornerstone": "CNR",
    "custodian investment": "CUS",
    "custodian": "CUS",
    "consolidated hallmark": "CHI",
    "coronation insurance": "INT",
    "coronation": "INT",
    "nem insurance": "NEM",
    "nem": "NEM",
    "prestige assurance": "PRE",
    "prestige": "PRE",
    "mutual benefits": "MBN",
    "mutual benefits assurance": "MBN",
    "sunu assurances": "SUN",
    "sunu": "SUN",
    "sovereign trust": "STI",
    "sovereign trust insurance": "STI",
    "royal exchange": "RYL",
    "regency alliance": "REG",
    "universal insurance": "UNIINSURE",
    "guinea insurance": "GIN",
    "great nigeria insurance": "GNI",
    "goldlink insurance": "GLK",
    "continental reinsurance": "CRL",

    # --- TELECOMS, TECHNOLOGY & DIGITAL SERVICES ---
    "briclinks": "BAP",
    "briclinks africa": "BAP",
    "ihs towers": "IHS",
    "ihs": "IHS",
    "legend internet": "LEG",
    "legend": "LEG",
    "starcomms": "STR",
    "mtech": "MTE",
    "mass telecom": "MTI",
    "cwg": "CWG",
    "ncr nigeria": "NCR",
    "ncr": "NCR",
    "omatek": "OMK",
    "tripple gee": "TGC",
    "the initiates": "INI",
    "initiates plc": "INI",

    # --- CEMENT, BUILDING MATERIALS & CONSTRUCTION ---
    "dangote cement plc": "DCE",
    "bua cement plc": "BUA",
    "lafarge wapco": "LWP",
    "ashaka cement": "ASH",
    "benue cement": "BEN",
    "cement company of the north": "CCN",
    "niger cement": "NCL",
    "arbico": "ARB",
    "cappa": "CDA",
    "cappa and d'alberto": "CDA",
    "costain": "COS",
    "g cappa": "GCL",
    "roads nigeria": "RNP",
    "ronchess": "RON",

    # --- CONSUMER GOODS, BREWERIES & FOOD ---
    "seven-up": "7UP",
    "seven up": "7UP",
    "7up": "7UP",
    "bua foods": "BUF",
    "dangote sugar": "DSR",
    "dangote sugar refinery": "DSR",
    "nascon": "NSC",
    "nascon allied": "NSC",
    "northern nigeria flour mills": "NNF",
    "nnfm": "NNF",
    "multi-trex": "MUA",
    "multi trex": "MUA",
    "nigeria bottling": "NBC",
    "nigerian bottling": "NBC",
    "utc nigeria": "UTC",
    "union dicon salt": "UDS",
    "champion breweries": "CHA",
    "champion brewery": "CHA",
    "international breweries": "IBL",
    "nigerian breweries": "NBL",
    "golden guinea": "GGL",
    "premier breweries": "PBL",
    "p z cussons": "PZN",
    "pz cussons": "PZN",
    "uac nigeria": "UAC",
    "uacn": "UAC",
    "transcorp": "TNC",
    "transnational corporation": "TNC",
    "honeywell flour": "HON",

    # --- OIL, GAS, POWER & ENERGY ---
    "aradel": "ARA",
    "aradel holdings": "ARA",
    "mrs oil": "CVX",
    "mrs": "CVX",
    "eterna": "ETR",
    "eterna oil": "ETR",
    "11 plc": "MOB",
    "mobil oil": "MOB",
    "japaul gold": "JAO",
    "japaul oil": "JAP",
    "global spectrum": "GSE",
    "transcorp power": "TNP",
    "geregu": "GRG",
    "geregu power": "GRG",
    "eunisell": "ESI",
    "eunisell interlinked": "ESI",
    "multiverse": "MUL",
    "nigerian energy sector fund": "UTESF",

    # --- AGRICULTURE & AGRO-ALLIED ---
    "livestock feeds": "LIV",
    "livestock": "LIV",
    "okomu oil palm": "OKM",
    "okomu": "OKM",
    "presco": "PRS",
    "ok itupupa oil palm": "OKI",
    "okitupupa oil palm": "OKI",
    "zichis agro": "ZAI",
    "zichis agro allied": "ZAI",

    # --- HEALTHCARE & PHARMACEUTICALS ---
    "fidson": "FIH",
    "fidson healthcare": "FIH",
    "glaxosmithkline": "GSK",
    "gsk": "GSK",
    "may and baker": "MAB",
    "may & baker": "MAB",
    "mecure": "MEC",
    "mecure industries": "MEC",
    "morison": "MIL",
    "morison industries": "MIL",
    "neimeth": "NIM",
    "pharma-deko": "PHA",
    "pharma deko": "PHA",
    "ekocorp": "EKO",
    "union diagnostic": "UDC",
    "evans medical": "EVM",

    # --- INDUSTRIALS, PACKAGING, CHEMICALS & PAINTS ---
    "beta glass": "BGC",
    "greif nigeria": "GNL",
    "nampak": "NAM",
    "poly products": "PPL",
    "studio press": "STU",
    "w a glass": "WAG",
    "berger paints": "BPN",
    "chemical and allied products": "CAP",
    "cap plc": "CAP",
    "meyer": "DNM",
    "notore": "NOT",
    "notore chemical": "NOT",
    "portland paints": "POR",
    "premier paints": "PPP",
    "industrial medical gases": "BOC",
    "first aluminium": "FAN",
    "vitafoam": "VIT",
    "vono": "VON",
    "cutix": "CUT",
    "nigerian wire": "NWC",

    # --- TRANSPORT, AVIATION, HOTELS, MEDIA & SERVICES ---
    "associated bus": "ABC",
    "newrest asl": "ASL",
    "sahco": "SAV",
    "nahco": "NAH",
    "nigerian aviation handling": "NAH",
    "medview airline": "MVA",
    "capital hotel": "CHL",
    "ikeja hotel": "IHL",
    "ikeja hotels": "IHL",
    "transcorp hotels": "THL",
    "tourist company of nigeria": "TCN",
    "red star express": "RED",
    "trans-national express": "TNE",
    "courtville": "COU",
    "afromedia": "AFR",
    "daar communications": "DCM",
    "academy press": "ACP",
    "learn africa": "LNL",
    "university press": "UPL",

    # --- REAL ESTATE, REITS & MORTGAGE ---
    "abbey mortgage": "ABB",
    "aso savings": "ASO",
    "infinity trust mortgage": "ITM",
    "resort savings": "RES",
    "union homes": "UHS",
    "living trust mortgage": "UTLIV",
    "updc property": "UAP",
    "updc reit": "UPT",
    "updc real estate investment trust": "UPT",
    "sfs real estate": "UTSKF",
    "uh real estate": "UHR",
    "haldane mccall": "HAL",
}

GENERIC_ALIAS_STOPWORDS = {
    "all",
    "big",
    "cap",
    "cut",
    "fan",
    "red",
    "sky",
    "union",
    "total",
    "access",
    "first",
    "united",
    "capital",
    "industrial",
    "media",
    "smart",
    "premium",
    "general",
    "living",
    "standard",
}

COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b(plc|public limited company|limited|ltd|company|co|corporation|corp|inc|"
    r"nigeria|nigerian|nig|holdings|holding|group|industries|industry|"
    r"international|integrated)\b",
    flags=re.IGNORECASE,
)


def build_ticker_aliases():
    """
    Build ticker aliases from the model-aligned ticker CSV, then layer manual
    human aliases on top. Manual aliases win; ambiguous CSV aliases are skipped.
    """

    manual_aliases = {
        normalize_alias(alias): ticker
        for alias, ticker in BROADSTREET_TICKERS.items()
        if normalize_alias(alias)
    }
    csv_aliases = load_ticker_csv_aliases()

    aliases = dict(manual_aliases)
    for alias, tickers in csv_aliases.items():
        if alias in aliases:
            continue
        if len(tickers) == 1:
            aliases[alias] = next(iter(tickers))

    return dict(sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True))


def load_ticker_csv_aliases():
    """Return aliases derived from data/master/tickers.csv, keyed to model ticker symbols."""

    tickers_path = next((path for path in TICKERS_CSV_CANDIDATES if path.exists()), None)
    if tickers_path is None:
        return {}

    try:
        tickers = pd.read_csv(tickers_path)
    except Exception as exc:
        print(f"Could not load ticker CSV aliases from {tickers_path}: {exc}")
        return {}

    alias_map = {}
    for _, row in tickers.iterrows():
        ticker = str(row.get("ticker", "")).strip().upper()
        name = str(row.get("name", "")).strip()
        if not ticker or not name:
            continue
        for alias in ticker_alias_variants(ticker, name):
            alias_map.setdefault(alias, set()).add(ticker)

    return alias_map


def ticker_alias_variants(ticker, company_name):
    """Generate conservative company-name variants from the canonical ticker CSV."""

    variants = {
        normalize_alias(company_name),
        normalize_alias(COMPANY_SUFFIX_PATTERN.sub(" ", company_name)),
        normalize_alias(re.sub(r"[&/().,-]", " ", company_name)),
        normalize_alias(COMPANY_SUFFIX_PATTERN.sub(" ", re.sub(r"[&/().,-]", " ", company_name))),
    }

    ticker_alias = normalize_alias(ticker)
    if len(ticker_alias) >= 3 and ticker_alias not in GENERIC_ALIAS_STOPWORDS:
        variants.add(ticker_alias)

    return {
        alias
        for alias in variants
        if alias
        and len(alias) >= 3
        and alias not in GENERIC_ALIAS_STOPWORDS
        and not alias.isdigit()
    }


def normalize_alias(value):
    """Normalize aliases for dictionary lookup."""

    text = str(value or "").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9.\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


TICKER_ALIASES = build_ticker_aliases()

# ============================================
# SECTOR & THEME TAGGER
# For articles with no specific ticker,
# identifies which sector/theme they affect
# ============================================

SECTOR_THEMES = {
    "oil_and_gas": [
        "oil", "gas", "crude", "petroleum", "nnpc", "opec",
        "pipeline", "refinery", "brent", "energy", "seplat",
        "oando", "fuel", "pms", "gulf", "iran", "saudi",
        "ndphc", "power supply", "electricity", "megawatt",
        "diesel", "subsidy", "fuel subsidy", "deregulation",
        "upstream", "downstream", "midstream", "lng", "nlng",
        "oil theft", "oil spill", "production quota", "output cut",
        "lifting cost", "petrol", "gas price", "power generation",
        "transmission", "grid collapse", "tariff hike", "metering",
    ],
    "banking_finance": [
        "bank", "cbn", "mpc", "interest rate", "monetary",
        "credit", "loan", "deposit", "crr", "ldr", "banks",
        "recapitalisation", "capital", "tier", "fintech",
        "microfinance", "pension", "n2.5tn", "n1.7 billion",
        "capital adequacy", "cash reserve", "treasury bills",
        "bond yield", "yield", "omo", "liquidity", "npl",
        "non-performing loan", "bad loan", "impairment",
        "dividend payout", "rights issue", "public offer",
        "commercial paper", "corporate bond", "credit rating",
    ],
    "politics_governance": [
        "election", "apc", "pdp", "senate", "governor",
        "president", "minister", "policy", "government",
        "federal", "regulation", "tax", "fiscal", "budget",
        "debt", "imf", "world bank", "disqualifies",
        "tribunal", "supreme court", "house of representatives",
        "national assembly", "executive order", "subsidy removal",
        "minimum wage", "strike", "protest", "labour union",
        "nass", "fg", "firs", "customs", "border closure",
        "import ban", "export ban", "policy uncertainty",
    ],
    "foreign_exchange": [
        "naira", "dollar", "fx", "foreign exchange",
        "exchange rate", "remittance", "import", "export",
        "devaluation", "cbdc",
        "forex", "parallel market", "official market", "nafem",
        "i&e window", "capital importation", "external reserves",
        "dollar shortage", "currency pressure", "naira depreciation",
        "naira appreciation", "exchange loss", "fx loss", "fx gain",
    ],
    "infrastructure": [
        "power", "electricity", "road", "railway", "port",
        "airport", "broadband", "telecoms", "5g", "fibre",
        "ndphc", "infrastructure", "construction", "1500mw",
        "1,500mw", "boost", "lagos power",
        "grid", "transmission company", "tcn", "concession",
        "public private partnership", "ppp", "toll", "rail",
        "deep seaport", "lekki port", "gas pipeline",
    ],
    "consumer_goods": [
        "inflation", "food", "price", "consumer", "fmcg",
        "manufacturing", "production", "supply chain",
        "import duty", "tariff",
        "purchasing power", "consumer spending", "food inflation",
        "raw material", "input cost", "wheat", "sugar", "cement price",
        "energy cost", "factory", "inventory", "margin pressure",
    ],
    "security": [
        "army", "military", "troops", "boko haram", "iswap",
        "bandits", "kidnap", "insecurity", "northeast",
        "conflict", "air strikes", "fighters",
        "pipeline vandalism", "militant", "insurgency", "curfew",
        "state of emergency", "civil unrest", "communal clash",
        "sabotage", "terror", "violence",
    ],
    "market_structure": [
        "ngx", "nse", "asi", "all-share index", "market cap",
        "market capitalization", "equities", "equity market",
        "stock market", "listing", "delisting", "suspension",
        "technical suspension", "free float", "cross deal",
        "block trade", "turnover", "breadth", "advancers",
        "decliners", "trading volume", "value traded",
    ],
    "corporate_actions": [
        "dividend", "bonus issue", "scrip dividend", "rights issue",
        "share reconstruction", "share split", "stock split",
        "scheme of arrangement", "merger", "acquisition",
        "takeover", "tender offer", "buyback", "agm", "egm",
        "qualification date", "closure of register", "payment date",
    ],
    "regulatory_legal": [
        "sec", "ngx regco", "fmdq", "firs", "pencom", "naicom",
        "sanction", "fine", "penalty", "probe", "investigation",
        "compliance", "breach", "lawsuit", "court", "judgment",
        "licence", "license", "approval", "forensic audit",
    ],
    "macro_economy": [
        "gdp", "growth", "recession", "inflation", "cpi",
        "interest rate", "unemployment", "pmi", "oil price",
        "fiscal deficit", "debt service", "sovereign rating",
        "credit outlook", "foreign investment", "portfolio inflow",
        "capital flight", "tax reform", "vat", "customs duty",
    ],
}

def tag_sector_theme(headline, article_text=""):
    """
    For articles with no specific ticker match,
    identifies which sector/theme they affect most.
    Returns a list of relevant themes.
    """
    combined = (headline + " " + article_text[:300]).lower()
    matched_themes = []

    for theme, keywords in SECTOR_THEMES.items():
        hits = sum(1 for word in keywords if word in combined)
        if hits >= 1:
            matched_themes.append((theme, hits))

    # Sort by number of hits — strongest theme first
    matched_themes.sort(key=lambda x: x[1], reverse=True)

    # Return just the theme names
    themes = [t[0] for t in matched_themes]

    return themes if themes else ["general_market"]

# ============================================
# STEP 3 — TEXT CLEANING FUNCTION
# ============================================

def clean_text(raw_text):
    
    # Remove HTML tags like <div>, <p>, <a href=...>
    text = re.sub(r'<[^>]+>', '', raw_text)
    
    # Remove HTML entities like &amp; &nbsp; &lt; &gt;
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    
    # Remove URLs — both http links and bare domains
    text = re.sub(r'http\S+|www\.\S+', '', text)
    
    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)
    
    # Remove social media handles and hashtags
    text = re.sub(r'[@#]\w+', '', text)
    
    # Remove emoji and non-ASCII characters
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Remove special characters — keep letters, numbers, spaces, % . , -
    text = re.sub(r'[^a-zA-Z0-9\s%.,\-]', '', text)
    
    # Collapse multiple spaces, tabs, newlines into one space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading and trailing space
    text = text.strip()
    
    return text

# ============================================
# STEP 4 — TICKER DETECTION FUNCTION
# ============================================

def find_tickers(headline):
    """
    Scans a headline for model-aligned ticker symbols and known aliases.
    Returns BroadStreet/model ticker symbols from data/master/tickers.csv.
    """
    headline_lower = normalize_alias(headline)
    found_tickers = []

    for keyword, ticker in TICKER_ALIASES.items():
        pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
        if re.search(pattern, headline_lower):
            # Avoid adding the same ticker twice
            if ticker not in found_tickers:
                found_tickers.append(ticker)

    return found_tickers

# ============================================
# STEP 5 — LOAD FINBERT
# ============================================

sentiment_model = None
sentiment_model_failed = False


def get_sentiment_model():
    """Lazy-load FinBERT so importing this module does not break the backend/tests."""

    global sentiment_model, sentiment_model_failed
    if sentiment_model is not None:
        return sentiment_model
    if sentiment_model_failed:
        return None
    if os.getenv("NUPAT_DISABLE_FINBERT") == "1":
        sentiment_model_failed = True
        print("FinBERT disabled by NUPAT_DISABLE_FINBERT=1; using keyword fallback only")
        return None

    print("Loading FinBERT... this takes about a minute the first time")
    try:
        sentiment_model = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            framework="pt",
        )
        print("FinBERT ready")
        return sentiment_model
    except Exception as exc:
        sentiment_model_failed = True
        print(f"FinBERT unavailable; using keyword fallback only ({exc})")
        return None

# ============================================
# KEYWORD BOOSTER
# Words that FinBERT consistently gets wrong
# in Nigerian financial context
# Add more as you discover them from real data
# ============================================

POSITIVE_KEYWORDS = [
    "profit", "gains", "growth", "rise", "rises", "rose",
    "surge", "surges", "beat", "beats", "strong", "record",
    "dividend", "expansion", "crosses", "up", "bullish",
    "acquisition", "milestone", "recovery", "positive",
    "upgrade", "outperform", "rally", "rallies", "jumps",
    "N500bn", "N100bn", "N200bn", "N300bn", "N400bn",
    "billion profit", "profit up", "revenue up", "earnings up",
    "subscribers", "users", "platform", "investment",
    "approval", "approved", "oversubscribed", "oversubscription",
    "bonus issue", "rights issue", "share buyback", "buyback",
    "merger approval", "acquires", "launches", "commissioned",
    "capacity expansion", "new plant", "higher dividend",
    "interim dividend", "final dividend", "special dividend",
    "margin improves", "margin improvement", "cost savings",
    "strong demand", "record high", "hits record", "market gains",
    "asi crosses", "all-share index rises", "market cap gains",
    "naira appreciates", "external reserves rise", "oil output rises",
    "crude output rises", "brent rises", "rate cut", "inflation eases",
    "pmi expands", "foreign inflows", "portfolio inflows",
    "credit rating upgrade", "stable outlook", "positive outlook",
    "regulatory approval", "licence renewal", "tax waiver",
]

NEGATIVE_KEYWORDS = [
    "loss", "losses", "fall", "falls", "fell", "decline",
    "declines", "declined", "drop", "drops", "dropped",
    "weak", "pressure", "headwinds", "concern", "concerns",
    "scrutiny", "risk", "risks", "slow", "slows", "slowed",
    "default", "defaults", "negative", "bearish", "sell",
    "downgrade", "underperform", "crash", "crashing",
    "debt", "lawsuit", "fine", "penalty", "suspended",
    "inflation", "volatility", "uncertainty", "warning",
    "probe", "investigation", "sanction", "breach", "fraud",
    "forensic audit", "court order", "judgment debt", "strike",
    "shutdown", "force majeure", "fire outbreak", "explosion",
    "pipeline vandalism", "oil spill", "grid collapse", "blackout",
    "fuel scarcity", "diesel price", "subsidy pressure",
    "tariff hike", "import ban", "export ban", "border closure",
    "tax hike", "windfall tax", "policy uncertainty",
    "naira depreciates", "naira weakens", "dollar shortage",
    "fx loss", "exchange loss", "devaluation", "capital flight",
    "external reserves fall", "oil output falls", "brent falls",
    "rate hike", "inflation rises", "food inflation", "pmi contracts",
    "credit rating downgrade", "negative outlook", "profit warning",
    "qualified opinion", "going concern", "delisting", "suspension",
    "loan defaults", "non-performing loans", "npl rises",
    "impairment charge", "margin pressure", "input cost",
    "insecurity", "civil unrest", "protest", "curfew",
]


def keyword_boost(cleaned_headline, finbert_label, finbert_confidence):
    """
    Checks headline for strong financial keywords.
    If FinBERT returned NEUTRAL but strong keywords exist,
    we override with the keyword signal.

    If FinBERT already returned POSITIVE or NEGATIVE,
    keywords can strengthen the confidence score.
    """

    headline_lower = cleaned_headline.lower()

    # Count how many positive and negative keywords appear
    positive_hits = sum(1 for word in POSITIVE_KEYWORDS if word.lower() in headline_lower)
    negative_hits = sum(1 for word in NEGATIVE_KEYWORDS if word.lower() in headline_lower)

    # Start with what FinBERT gave us
    final_label      = finbert_label
    final_confidence = finbert_confidence

    # ── Case 1: FinBERT said NEUTRAL but keywords disagree ──
    if finbert_label == "neutral":
        if positive_hits > negative_hits:
            final_label      = "positive"
            # Confidence based on how many keywords matched
            final_confidence = min(0.55 + (positive_hits * 0.05), 0.85)
        elif negative_hits > positive_hits:
            final_label      = "negative"
            final_confidence = min(0.55 + (negative_hits * 0.05), 0.85)
        # If equal hits, keep neutral

    # ── Case 2: FinBERT said POSITIVE, keywords agree — boost it ──
    elif finbert_label == "positive" and positive_hits > 0:
        boost            = positive_hits * 0.02
        final_confidence = min(finbert_confidence + boost, 0.98)

    # ── Case 3: FinBERT said NEGATIVE, keywords agree — boost it ──
    elif finbert_label == "negative" and negative_hits > 0:
        boost            = negative_hits * 0.02
        final_confidence = min(finbert_confidence + boost, 0.98)

    return final_label, round(final_confidence, 4)

def process_headline(raw_headline):
    """
    Full pipeline — now includes keyword booster
    to catch what FinBERT misses on Nigerian headlines
    """

    # Step 1 — Clean
    cleaned = clean_text(raw_headline)

    # Step 2 — Find tickers
    tickers = find_tickers(raw_headline)

    # Step 3 — FinBERT sentiment
    model = get_sentiment_model()
    if model is None:
        finbert_label = "neutral"
        finbert_confidence = 0.50
    else:
        sentiment_result    = model(cleaned)[0]
        finbert_label       = sentiment_result['label']
        finbert_confidence  = sentiment_result['score']

    # Step 4 — Keyword booster
    final_label, final_confidence = keyword_boost(
        cleaned,
        finbert_label,
        finbert_confidence
    )

    return {
        "original"        : raw_headline,
        "cleaned"         : cleaned,
        "tickers"         : tickers,
        "sentiment"       : final_label,
        "confidence"      : round(final_confidence * 100, 1),
        "finbert_original": finbert_label,   # keeping this for comparison
    }

# ============================================
# STEP 8 — CONVERT SENTIMENT LABEL TO NUMBER
# This turns words into numbers so we can 
# do maths with them
# positive  →  1.0
# neutral   →  0.0
# negative  → -1.0
# ============================================

def label_to_number(label):
    if label == "positive":
        return 1.0
    elif label == "negative":
        return -1.0
    else:
        return 0.0
    
def aggregate_one_stock(ticker, headlines_for_ticker):
    """
    Updated version with:
    - Confidence penalty for low headline counts
    - Adjusted signal thresholds
    """

    if not headlines_for_ticker:
        return {
            "ticker"         : ticker,
            "final_score"    : 0.0,
            "signal"         : "NEUTRAL",
            "headline_count" : 0,
            "breakdown"      : []
        }

    weighted_scores = []
    weights         = []
    breakdown       = []

    for headline in headlines_for_ticker:

        result     = process_headline(headline)
        label      = result['sentiment']
        confidence = result['confidence']

        # Make sure confidence is in decimal form
        if confidence > 1:
            confidence = confidence / 100

        numeric = label_to_number(label)

        weighted_scores.append(numeric * confidence)
        weights.append(confidence)

        breakdown.append({
            "headline"  : headline[:80],
            "sentiment" : label,
            "confidence": round(confidence * 100, 1),
            "score"     : round(numeric * confidence, 4)
        })

    # Calculate raw weighted average
    total_weight = sum(weights)
    raw_score    = sum(weighted_scores) / total_weight

    # ─────────────────────────────────────────
    # FIX A — Confidence penalty for thin data
    # The fewer headlines we have, the more we
    # pull the score toward 0 (neutral/uncertain)
    #
    # 1 headline  → 40% penalty (score × 0.60)
    # 2 headlines → 20% penalty (score × 0.80)
    # 3 headlines → 10% penalty (score × 0.90)
    # 4+ headlines → no penalty (score × 1.00)
    # ─────────────────────────────────────────
    count = len(headlines_for_ticker)

    if count == 1:
        confidence_multiplier = 0.60
    elif count == 2:
        confidence_multiplier = 0.80
    elif count == 3:
        confidence_multiplier = 0.90
    else:
        confidence_multiplier = 1.00

    final_score = round(raw_score * confidence_multiplier, 4)

    # ─────────────────────────────────────────
    # FIX B — Adjusted signal thresholds
    # Slightly wider NEUTRAL band means we only
    # fire POSITIVE or NEGATIVE when we're 
    # genuinely confident in the signal
    # ─────────────────────────────────────────
    if final_score >= 0.35:
        signal = "POSITIVE"
    elif final_score <= -0.35:
        signal = "NEGATIVE"
    else:
        signal = "NEUTRAL"

    return {
        "ticker"         : ticker,
        "final_score"    : final_score,
        "signal"         : signal,
        "headline_count" : count,
        "breakdown"      : breakdown
    }

# ============================================
# STEP 10 — GROUP HEADLINES BY TICKER
# Takes the full list of processed headlines
# and organises them by which stock they mention
# ============================================

def group_headlines_by_ticker(raw_headlines):
    """
    Input  : a flat list of raw headlines (mixed, all stocks)
    Output : a dictionary where each key is a ticker
             and the value is a list of headlines mentioning it
    
    Also separately collects macro headlines 
    (no ticker found) for market-wide context
    """

    grouped = {}   # ticker → list of headlines
    macro   = []   # headlines with no specific stock

    for headline in raw_headlines:
        tickers = find_tickers(headline)

        if not tickers:
            # No stock mentioned — this is a macro/market headline
            macro.append(headline)
        else:
            # Add headline under each ticker it mentions
            for ticker in tickers:
                if ticker not in grouped:
                    grouped[ticker] = []
                grouped[ticker].append(headline)

    return grouped, macro

FETCHERS = [
    {
        "name"        : "NGX Announcements",
        "module"      : "ngx_announcements",
        "class"       : "NGXAnnouncementsFetcher",
        "ticker_mode" : "pre_tagged",
        "priority"    : 1,
    },
    {
        "name"        : "BusinessDay",
        "module"      : "businessday",
        "class"       : "BusinessDayFetcher",
        "ticker_mode" : "needs_tagging",
        "priority"    : 2,
    },
    {
        "name"        : "Nairametrics",
        "module"      : "nairametrics",
        "class"       : "NairametricsFetcher",
        "ticker_mode" : "needs_tagging",
        "priority"    : 2,
    },
    # Add remaining fetchers as they get built
]

# def load_all_news(since_days_ago=1):
#     # tries every fetcher in FETCHERS
#     # skips NotImplementedError ones silently
#     # returns combined DataFrame
#     pass

def load_all_news(since_days_ago=14):
    """
    Loads articles from saved fetcher output files.
    Falls back to mock data if no real data exists yet.
    """
    from pathlib import Path

    processed_path = Path("data/output/processed/news/articles")
    all_frames     = []

    # ── Look for any parquet files the fetchers have saved ──
    parquet_files = list(processed_path.rglob("*.parquet"))

    if not parquet_files:
        print("  No fetcher output found.")
        print("  Run the news fetchers first, for example:")
        print("  python -m data.pipeline news")
        return pd.DataFrame()
    
    for parquet_file in parquet_files:
        try:
            df = pd.read_parquet(parquet_file)

            # Fix timezone — convert everything to UTC first
            df['published_date'] = pd.to_datetime(df['published_date'], utc=True)

            # Create cutoff in UTC
            since = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=since_days_ago)

            # Filter — both sides are now UTC, comparison works correctly
            df = df[df['published_date'] >= since]

            if df.empty:
                print(f"  {parquet_file.parent.parent.name}: no recent articles")
                continue

            # Tag ticker mode based on source column
            df['ticker_mode'] = df['source'].apply(
                lambda s: "pre_tagged" if s == "ngx_announcements"
                else "needs_tagging"
            )

            print(f"  {parquet_file.parent.parent.name}: {len(df)} articles loaded ✓")
            all_frames.append(df)

        except Exception as e:
            print(f"  {parquet_file.name}: failed to load ({e})")
    

    if not all_frames:
        print("  No articles found in the date range.")
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["headline"])
    combined = combined.reset_index(drop=True)

    print(f"\n  Total articles : {len(combined)}")
    print(f"  Sources        : {combined['source'].unique().tolist()}")

    return combined

def prepare_articles(df):
    """
    Processes the combined DataFrame and returns
    a list of clean dicts ready for aggregation.
    """

    prepared = []

    for _, row in df.iterrows():
        headline     = str(row.get("headline", "")).strip()
        article_text = str(row.get("article_text", "")).strip()
        ticker_mode  = row.get("ticker_mode", "needs_tagging")
        source       = row.get("source", "unknown")

        # Skip rows with no headline
        if not headline or headline == "nan":
            continue

        # ── Build text for sentiment analysis ──
        if article_text and article_text != "nan":
            body_preview        = article_text[:500]
            text_for_sentiment  = f"{headline}. {headline}. {body_preview}"
        else:
            text_for_sentiment = headline

        # ── Determine tickers ──
        if ticker_mode == "pre_tagged":
            raw_tickers = row.get("mentioned_tickers", [])

            # Handle numpy array
            if hasattr(raw_tickers, 'tolist'):
                raw_tickers = raw_tickers.tolist()

            # Handle string
            if isinstance(raw_tickers, str):
                import ast
                try:
                    raw_tickers = ast.literal_eval(raw_tickers)
                except Exception:
                    raw_tickers = []

            # Handle None
            if raw_tickers is None:
                raw_tickers = []

            tickers = list(raw_tickers) if len(raw_tickers) > 0 else []

        else:
            # Run our keyword detection on the headline
            tickers = find_tickers(headline)

        # Tag sector theme for articles with no ticker
        if not tickers:
            themes = tag_sector_theme(headline, article_text)
        else:
            themes = []

        prepared.append({
            "original_headline" : headline,
            "text_for_sentiment": text_for_sentiment,
            "tickers"           : tickers,
            "themes"            : themes,
            "source"            : source,
        })

    print(f"  {len(prepared)} articles prepared for sentiment analysis")
    print(f"  {sum(1 for p in prepared if p['tickers'])} have ticker matches")
    print(f"  {sum(1 for p in prepared if not p['tickers'])} are macro/general")

    return prepared

# ============================================
# STEP 11 — THE FULL DAILY AGGREGATOR
# This is the main function that runs once a day
# Feed it ALL the day's headlines in one list
# It returns a complete sentiment report
# ============================================

def run_daily_aggregator_v2(prepared_articles, date=None):
    """
    Updated aggregator that works with the
    prepared article dicts from prepare_articles().
    Everything else stays the same as before.
    """

    from datetime import datetime
    if date is None:
        date = datetime.today().strftime('%Y-%m-%d')

    print(f"\n{'=' * 60}")
    print(f"  NUPAT AI — DAILY SENTIMENT REPORT")
    print(f"  Date: {date}")
    print(f"  Total articles: {len(prepared_articles)}")
    print(f"{'=' * 60}\n")

    # Group articles by ticker
    grouped = {}  # ticker → list of text_for_sentiment strings
    macro   = []  # no ticker found

    for article in prepared_articles:
        tickers = article['tickers']
        text    = article['text_for_sentiment']

        if not tickers:
            macro.append(text)
        else:
            for ticker in tickers:
                if ticker not in grouped:
                    grouped[ticker] = []
                grouped[ticker].append(text)

    print(f"  Stocks with coverage today : {len(grouped)}")
    print(f"  Macro/general articles     : {len(macro)}")
    print(f"\n  Processing...\n")

    # Aggregate sentiment per stock
    stock_reports = []
    for ticker, texts in grouped.items():
        report = aggregate_one_stock(ticker, texts)
        stock_reports.append(report)

    stock_reports.sort(key=lambda x: x['final_score'], reverse=True)

    # ── Aggregate by sector theme ──
    themed = {}   # theme → list of texts

    for article in prepared_articles:
        themes = article.get('themes', [])
        text   = article['text_for_sentiment']

        for theme in themes:
            if theme not in themed:
                themed[theme] = []
            themed[theme].append(text)

    # Aggregate sentiment per theme
    theme_reports = []
    for theme, texts in themed.items():
        report = aggregate_one_stock(theme, texts)
        theme_reports.append(report)

    theme_reports.sort(key=lambda x: x['final_score'], reverse=True)


    # Aggregate macro headlines
    macro_score = None
    if macro:
        macro_score = aggregate_one_stock("MARKET_WIDE", macro)

    # Print the report table
    print(f"{'─' * 60}")
    print(f"  {'TICKER':<12} {'SCORE':>8}  {'SIGNAL':<10} {'ARTICLES':>10}")
    print(f"{'─' * 60}")

    for r in stock_reports:
        arrow = "▲" if r['signal'] == "POSITIVE" else \
                "▼" if r['signal'] == "NEGATIVE" else "─"
        print(
            f"  {r['ticker']:<12} "
            f"{r['final_score']:>8.4f}  "
            f"{arrow} {r['signal']:<10} "
            f"{r['headline_count']:>5} article(s)"
        )

    if macro_score:
        arrow = "▲" if macro_score['signal'] == "POSITIVE" else \
                "▼" if macro_score['signal'] == "NEGATIVE" else "─"
        print(f"{'─' * 60}")
        print(
            f"  {'MARKET_WIDE':<12} "
            f"{macro_score['final_score']:>8.4f}  "
            f"{arrow} {macro_score['signal']:<10} "
            f"{macro_score['headline_count']:>5} article(s)"
        )

    print(f"{'─' * 60}")

    # ── Aggregate by sector theme ──
    themed = {}

    for article in prepared_articles:
        themes = article.get('themes', [])
        text   = article['text_for_sentiment']
        for theme in themes:
            if theme not in themed:
                themed[theme] = []
            themed[theme].append(text)

    theme_reports = []
    for theme, texts in themed.items():
        report = aggregate_one_stock(theme, texts)
        theme_reports.append(report)

    theme_reports.sort(key=lambda x: x['final_score'], reverse=True)

    if theme_reports:
        print(f"\n{'─' * 60}")
        print(f"  SECTOR & THEME SENTIMENT")
        print(f"{'─' * 60}")
        print(f"  {'THEME':<22} {'SCORE':>8}  {'SIGNAL':<10} {'ARTICLES':>8}")
        print(f"{'─' * 60}")

        for r in theme_reports:
            arrow = "▲" if r['signal'] == "POSITIVE" else \
                    "▼" if r['signal'] == "NEGATIVE" else "─"
            print(
                f"  {r['ticker']:<22} "
                f"{r['final_score']:>8.4f}  "
                f"{arrow} {r['signal']:<10} "
                f"{r['headline_count']:>5} article(s)"
            )

    # Add theme_reports to the return value
    return {
        "date"          : date,
        "stock_scores"  : stock_reports,
        "macro_score"   : macro_score,
        "theme_reports" : theme_reports,
        "total_articles": len(prepared_articles)
    }

    

def load_macro_data():
    """
    Loads real macro data from parquet files
    already saved by the scraping team.
    """
    from pathlib import Path
    import pandas as pd

    macro = {}

    # ── CBN Exchange Rates ──
    try:
        cbn_path = Path("data/output/processed/macro/cbn_exchange_rates.parquet")

        if cbn_path.exists():
            print("  Loading CBN exchange rates...")
            fx_df = pd.read_parquet(cbn_path)

            latest_fx = (
                fx_df.sort_values("date")
                     .groupby("indicator")
                     .last()
                     .reset_index()
            )

            for _, row in latest_fx.iterrows():
                macro[row["indicator"]] = {
                    "value" : round(float(row["value"]), 2),
                    "unit"  : row["unit"],
                    "date"  : str(pd.Timestamp(row["date"]).date()),
                    "source": "cbn"
                }

            print(f"  CBN: {len(latest_fx)} exchange rates loaded ✓")
        else:
            print("  CBN: parquet file not found")

    except Exception as e:
        print(f"  CBN: failed ({e}) — skipping")

    # ── Brent Crude Oil ──
    try:
        yahoo_path = Path("data/output/processed/macro/yahoo_macro.parquet")

        if yahoo_path.exists():
            print("  Loading Brent crude oil price...")
            oil_df = pd.read_parquet(yahoo_path)

            brent = oil_df[oil_df["indicator"] == "brent_oil_usd"]

            if not brent.empty:
                latest = brent.sort_values("date").iloc[-1]
                macro["brent_oil_usd"] = {
                    "value" : round(float(latest["value"]), 2),
                    "unit"  : "USD/barrel",
                    "date"  : str(pd.Timestamp(latest["date"]).date()),
                    "source": "yahoo"
                }
                print(f"  Brent Oil: ${macro['brent_oil_usd']['value']}/barrel ✓")
            else:
                print("  Brent Oil: no brent_oil_usd rows found")
        else:
            print("  Yahoo: parquet file not found")

    except Exception as e:
        print(f"  Yahoo: failed ({e}) — skipping")

    return macro

def export_for_backend(daily_report, include_macro=True):
    """
    Exports the complete daily package for the backend team.
    Includes sentiment scores + macro indicators in one JSON file.
    """

    package = {
        "date"            : daily_report['date'],
        "generated_at"    : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "total_articles"  : daily_report['total_articles'],

        "stock_sentiments": [
            {
                "ticker"         : s['ticker'],
                "sentiment_score": s['final_score'],
                "signal"         : s['signal'],
                "article_count"  : s['headline_count'],
            }
            for s in daily_report['stock_scores']
        ],
        # Add to the package dictionary
"theme_sentiments": [
    {
        "theme"          : r['ticker'],
        "sentiment_score": r['final_score'],
        "signal"         : r['signal'],
        "article_count"  : r['headline_count'],
    }
    for r in theme_reports
] if 'theme_reports' in dir() else [],

        "market_sentiment": {
            "score"        : daily_report['macro_score']['final_score'],
            "signal"       : daily_report['macro_score']['signal'],
            "article_count": daily_report['macro_score']['headline_count'],
        } if daily_report.get('macro_score') else None,

        "macro_indicators": {}
    }
    

    # Add macro data if requested
    if include_macro:
        print("  Loading macro indicators...")
        macro_data = load_macro_data()
        package["macro_indicators"] = macro_data

    # Save to JSON file
    filename = f"nupat_daily_package_{daily_report['date']}.json"
    with open(filename, 'w') as f:
        json.dump(package, f, indent=4)

    print(f"\n  Package saved : {filename}")
    print(f"  Stocks covered   : {len(package['stock_sentiments'])}")
    print(f"  Macro indicators : {len(package['macro_indicators'])}")

    return package


def run_pipeline(since_days_ago=14):
    """
    Complete end-to-end pipeline.
    One function call runs everything and
    produces one JSON file for the backend team.
    Step 1 — load_all_news()
    Step 2 — prepare_articles()
    Step 3 — run_daily_aggregator_v2()
    Step 4 — export_for_backend()
    """

    todays_date = date.today().strftime('%Y-%m-%d')

    print("=" * 60)
    print("  NUPAT AI — FULL PIPELINE")
    print(f"  Date : {todays_date}")
    print("=" * 60)

    # ── Step 1 — Load articles from all available sources ──
    print("\nSTEP 1 — Loading news sources...")
    print()
    df = load_all_news(since_days_ago=since_days_ago)

    if df.empty:
        print("No articles found. Run the real news fetch pipeline first.")
        print("Example: python -m data.pipeline news")
        return None

    # ── Step 2 — Prepare articles for sentiment analysis ──
    print("\nSTEP 2 — Preparing articles...")
    print()
    prepared = prepare_articles(df)

    if not prepared:
        print("No articles could be prepared. Exiting.")
        return None

    # ── Step 3 — Run sentiment aggregator ──
    print("\nSTEP 3 — Running sentiment aggregator...")
    daily_report = run_daily_aggregator_v2(prepared, date=todays_date)

    # ── Step 4 — Export package for backend team ──
    print("\nSTEP 4 — Exporting package for backend team...")
    print()
    package = export_for_backend(daily_report, include_macro=True)

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print(f"  Output: nupat_daily_package_{todays_date}.json")
    print("=" * 60)

    return daily_report, package

# ── Entry point ───────────────────────────────────
if __name__ == "__main__":
    result = run_pipeline(since_days_ago=14)
