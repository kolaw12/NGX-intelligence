# NGX Intelligence

NGX Intelligence is an AI-powered Nigerian Exchange market intelligence platform.
It combines real NGX market data, XGBoost-based prediction, optional LSTM
support, risk scoring, sentiment analysis, recommendations, and a React
dashboard for investors and analysts.

## Repository Structure

```text
backend/      FastAPI backend, ML inference, market data, sentiment pipeline
frontend/     React/Vite frontend dashboard
presentation/ Project presentation deck
```

## Core Production Flow

```text
Frontend
→ FastAPI backend
→ Market data service
→ Feature engineering
→ XGBoost prediction engine
→ Optional LSTM support
→ Risk and sentiment engines
→ Recommendation and explanation response
```

XGBoost is the main production model. LSTM is optional and does not block
backend inference when disabled or missing.

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-web.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health checks:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/api/v1/model/status
http://127.0.0.1:8000/api/v1/engine/health
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Set `frontend/.env` from `frontend/.env.example`:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_USE_MOCK=false
```

## Deployment

Recommended simple deployment:

```text
Backend  → Railway
Frontend → Vercel
```

Backend deployment files are in `backend/`:

```text
railway.json
requirements-web.txt
Procfile
DEPLOYMENT.md
```

Frontend deployment files are in `frontend/`:

```text
vercel.json
.nvmrc
DEPLOYMENT.md
```

Deploy backend first, copy its public URL, then set frontend:

```bash
VITE_API_BASE_URL=https://YOUR_BACKEND_URL/api/v1
```

Then update backend CORS:

```bash
FRONTEND_URL=https://YOUR_FRONTEND_URL
```

## Important Model Files

```text
backend/models/xgboost_model.pkl
backend/models/xgb_feature_list.json
backend/models/feature_list.json
backend/models/backend_model_config.json
```

The backend loads trained artifacts only. It does not retrain models in the web
server.

## Safety

Do not commit:

```text
.env
private credentials
API keys
local databases
node_modules/
```

