# Deployment Quick Start

This monorepo can be deployed without needing access to the original
organization repositories.

## 1. Backend on Railway

```bash
cd backend
railway login
railway init --name ngx-intelligence-api
railway up --detach --message "deploy backend api"
railway domain
```

Set backend environment variables in Railway:

```bash
APP_ENV=production
ENV=production
LOG_LEVEL=INFO
NUPAT_DISABLE_FINBERT=1
FRONTEND_URL=https://YOUR_FRONTEND_URL
```

If you use Railway Postgres, set:

```bash
DATABASE_URL=postgresql://...
```

## 2. Frontend on Vercel

```bash
cd frontend
vercel login
vercel --prod
```

Set frontend environment variables:

```bash
VITE_API_BASE_URL=https://YOUR_BACKEND_URL/api/v1
VITE_USE_MOCK=false
```

## 3. Verify

Backend:

```text
/health
/api/v1/model/status
/api/v1/engine/health
/api/v1/news
```

Frontend:

```text
/app
/app/stocks
/app/markets
```

