# NGX AI Stock Broker Backend

Production FastAPI backend for an AI-powered Nigerian Exchange (NGX) stock intelligence platform.

This service powers market dashboards, stock detail pages, watchlists, portfolios, alerts, model status checks, and XGBoost-first BUY/HOLD/SELL recommendations. The backend is designed to run inference from trained artifacts only. It does not retrain models in production.

## Current Production Position

- XGBoost is the primary production prediction model.
- LSTM is optional and non-blocking.
- Missing LSTM artifacts must not break API startup or prediction.
- Recommendations use model probability, risk, sentiment, and data-quality checks.
- Missing real data is reported as unavailable instead of being fabricated.

## Architecture

```text
Frontend
  -> FastAPI API
  -> Market data service
  -> Feature engineering
  -> XGBoost predictor
  -> Optional LSTM predictor
  -> Risk engine
  -> Sentiment engine or neutral fallback
  -> Recommendation engine
  -> Explanation engine
```

## Key Features

- FastAPI application with versioned `/api/v1` routes
- XGBoost model loaded once and reused for inference
- Training feature order enforced from JSON feature list
- Optional LSTM support controlled by backend config
- Real risk scoring from engineered price/volume features
- News sentiment ingestion with neutral fallback when NLP data is missing
- Model and engine health endpoints
- User authentication, watchlists, portfolio, alerts, settings, and API tokens
- In-memory TTL caching for expensive read endpoints
- Local SQLite fallback for development
- PostgreSQL-ready SQLAlchemy models and Alembic setup

## Repository Layout

```text
app/
  main.py                         FastAPI application factory
  routers/                        API routes
  services/                       Model, data, risk, sentiment, cache, and feature services
  db/                             SQLAlchemy models and data access helpers
  explain/                        SHAP/NLG explanation helpers
  utils/                          Shared enums and utilities

models/
  xgboost_model.pkl               Main XGBoost model artifact
  xgb_feature_list.json           XGBoost feature order
  feature_list.json               Fallback feature order
  backend_model_config.json       Model selection/configuration

data/
  master/                         Ticker metadata
  output/processed/               Processed market, macro, and news data

scripts/
  refresh_data.py                 Data refresh entry point
  test_real_pipeline.py           End-to-end inference smoke test

alembic/                          Database migration scaffold
```

## Important Model Files

Required for XGBoost production inference:

```text
models/xgboost_model.pkl
models/xgb_feature_list.json
```

Fallback feature list:

```text
models/feature_list.json
```

Backend model config:

```text
models/backend_model_config.json
```

Optional LSTM artifacts:

```text
models/lstm_model.keras
models/lstm_model.h5
models/lstm_scaler.pkl
scalers/lstm_scaler.pkl
```

LSTM is used only when config enables it and required artifacts are present.
Keras/TensorFlow are intentionally not installed by the base production requirements because LSTM is experimental and optional. Install a patched Keras/TensorFlow stack separately only in environments where `use_lstm=true`.

## API Endpoints

Health and engine:

```text
GET /health
GET /api/v1/health
GET /api/v1/model/status
GET /api/v1/engine/health
GET /api/v1/engine/health?deep=true
```

Prediction and recommendations:

```text
POST /api/v1/predict
GET  /api/v1/recommendations
GET  /api/v1/recommendations/{symbol}
```

Market and stocks:

```text
GET /api/v1/market/overview
GET /api/v1/sectors
GET /api/v1/stocks
GET /api/v1/stocks/{symbol}
GET /api/v1/stocks/{symbol}/ohlc
GET /api/v1/stocks/{symbol}/line
GET /api/v1/stocks/{symbol}/fundamentals
GET /api/v1/stocks/{symbol}/peers
```

News and sentiment:

```text
GET  /api/v1/news
GET  /api/v1/news/sentiment-summary
GET  /api/v1/news/sentiment-diagnostics
POST /api/v1/news/rebuild-sentiment
```

Auth and user data:

```text
POST /api/v1/auth/signup
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/logout

GET  /api/v1/watchlists
POST /api/v1/watchlists
POST /api/v1/watchlists/{watchlist_id}/symbols
DELETE /api/v1/watchlists/{watchlist_id}/symbols/{symbol}

GET  /api/v1/portfolio
POST /api/v1/portfolio/positions
DELETE /api/v1/portfolio/positions/{symbol}

GET  /api/v1/alerts
POST /api/v1/alerts
DELETE /api/v1/alerts/{alert_id}
```

Account settings:

```text
PUT /api/v1/profile
GET /api/v1/profile/settings
PUT /api/v1/profile/settings
GET /api/v1/api-tokens
POST /api/v1/api-tokens
DELETE /api/v1/api-tokens/{token_id}
```

## Example Prediction Request

```bash
curl -X POST http://127.0.0.1:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "GTCO",
    "features": {
      "log_ret": 0.012,
      "daily_ret": 0.011,
      "RSI_14": 58.2
    }
  }'
```

Example response shape:

```json
{
  "ticker": "GTCO",
  "action": "HOLD",
  "up_probability": 0.5421,
  "confidence": 0.0842,
  "main_model": "xgboost",
  "model_source": "xgboost_only",
  "reason": "The model sees mild upside probability, but confidence is not strong enough for BUY."
}
```

## Recommendation Logic

Base probability rule:

```text
up_probability >= 0.60 -> BUY
up_probability <= 0.40 -> SELL
otherwise              -> HOLD
```

Confidence:

```text
confidence = abs(up_probability - 0.5) * 2
```

Risk and sentiment can downgrade a BUY to HOLD when:

- risk score is high
- sentiment is materially negative
- confidence is too low
- data quality is poor

## Environment Variables

Copy `.env.example` and provide real values where needed.

```text
ENV=development
LOG_LEVEL=INFO
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/ngx_ai
FRONTEND_URL=http://localhost:5173
AUTH_SECRET=change-me
AUTH_SALT=change-me
DATA_OUTPUT_DIR=data/output
DATA_LOG_DIR=data/logs
XGB_ENSEMBLE_WEIGHT=0.60
LSTM_ENSEMBLE_WEIGHT=0.40
```

Do not commit `.env` or private credentials.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

## Verification

Compile Python files:

```bash
python -m compileall .
```

Run tests:

```bash
pytest
```

Run dependency check:

```bash
pip check
```

Run the real inference pipeline:

```bash
python scripts/test_real_pipeline.py GTCO
```

Expected result:

- XGBoost model loads
- feature list loads
- latest ticker data loads
- features are built in training order
- XGBoost probability is produced
- risk and sentiment are evaluated
- final recommendation is returned

## Data Sources

The backend currently reads processed local artifacts from:

```text
data/master/tickers.csv
data/output/processed/prices/
data/output/processed/macro/
data/output/processed/news/
data/output/processed/fundamentals/
```

Fundamentals are optional. If no real fundamentals export is present, company profile and valuation fields remain unavailable rather than being faked.

Supported fundamentals file names include:

```text
data/output/processed/fundamentals/fundamentals.csv
data/output/processed/fundamentals/fundamentals.parquet
data/output/processed/fundamentals/company_profiles.csv
data/output/processed/fundamentals/company_profiles.parquet
```

## Deployment Notes

Recommended deployment:

```text
Frontend: Vercel
Backend: Railway, Render, or Fly.io
Database: PostgreSQL
Artifacts: repository for small files, object storage or Git LFS for larger files
```

Production start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Production health checks:

```text
/health
/api/v1/model/status
/api/v1/engine/health
```

## Security Notes

- Do not commit `.env`
- Do not commit private API keys or credentials
- Use strong `AUTH_SECRET` and `AUTH_SALT` in production
- Store external service credentials in deployment secrets
- Keep `FRONTEND_URL` restricted to trusted origins
- Use PostgreSQL for production persistence

## Current Limitations

- Fundamentals are only available when real CSV/parquet exports are provided.
- Sentiment falls back to neutral when ticker-specific NLP data is unavailable.
- LSTM is experimental and disabled unless explicitly enabled by config.
- Model artifacts should move to object storage or Git LFS if they grow significantly.

## License

Proprietary. Internal development for NUPAT Technologies.
