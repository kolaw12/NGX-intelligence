import os
from dotenv import load_dotenv

load_dotenv()

# Credentials
BROADSTREET_USERNAME = os.getenv("BROADSTREET_USERNAME")
BROADSTREET_PASSWORD = os.getenv("BROADSTREET_PASSWORD")

# Endpoints
BASE_URL = os.getenv("BASE_URL")
LOGIN_ENDPOINT = os.getenv("LOGIN_ENDPOINT")

# HTTP politeness (override via .env if needed)
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36",
)
FROM_EMAIL = os.getenv("FROM_EMAIL", "data-team@nupat.local")
REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "2.0"))
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "3.0"))
# 60s default handles slow-responding sites like ngxgroup.com without
# inflating the politeness budget. If a specific fetcher is still timing
# out, set REQUEST_TIMEOUT=90 (or higher) in .env.
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))

# Paths
DATA_DIR = "data"
MASTER_DIR = f"{DATA_DIR}/master"
RAW_DIR = f"{DATA_DIR}/output/raw/broadstreet"
PROCESSED_DIR = f"{DATA_DIR}/output/processed"
LOG_DIR = f"{DATA_DIR}/logs"

# Operator-controlled killswitch (touch this file to abort the next request)
KILLSWITCH_PATH = f"{DATA_DIR}/.killswitch"
