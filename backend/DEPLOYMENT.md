# NGX Intelligence Backend Deployment

Recommended host: Render, Railway, or any Python web service that supports
FastAPI.

## Railway CLI deployment

This repo includes `railway.json`, which uses the lightweight
`requirements-web.txt` for the hosted API.

```bash
railway init --name ngx-intelligence-api
railway up --detach --message "deploy backend api"
railway domain
```

## Start command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Required environment variables

```bash
APP_ENV=production
ENV=production
LOG_LEVEL=INFO
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/ngx_ai
FRONTEND_URL=https://YOUR_FRONTEND_URL
NUPAT_DISABLE_FINBERT=1
```

Use `FRONTEND_URLS` for multiple allowed frontend origins:

```bash
FRONTEND_URLS=https://main-frontend.example.com,https://preview-frontend.example.com
```

## Why FinBERT is disabled by default on hosted API

The production API reads the generated sentiment package JSON first, so it does
not need to load the heavy FinBERT model on every web server start. Run the
sentiment pipeline as a scheduled job, then let the API serve the latest JSON.

For a stronger production setup, run FinBERT in a scheduled worker with enough
memory, not inside the request path.

## Health checks

After deployment, check:

```bash
GET /health
GET /api/v1/engine/health
GET /api/v1/model/status
GET /api/v1/news
```

## Deployment order

1. Deploy backend first.
2. Copy the backend public URL.
3. Set frontend `VITE_API_BASE_URL` to `https://BACKEND_URL/api/v1`.
4. Deploy frontend.
5. Set backend `FRONTEND_URL` to the frontend URL.
