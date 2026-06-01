# NGX Intelligence Frontend

Professional React frontend for the NGX Intelligence stock market platform. The application provides dashboards, market views, stock detail pages, AI insights, portfolio tools, alerts, watchlists, and administration screens backed by the NGX AI backend API.

## Stack

- React 18
- TypeScript
- Vite
- Tailwind CSS
- TanStack React Query
- React Router
- ECharts
- Radix UI primitives
- Zustand

## Requirements

- Node.js 20+
- npm 10+
- Running NGX Intelligence backend API

## Environment

Create a local `.env` file from `.env.example`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_USE_MOCK=false
```

For production hosting, set `VITE_API_BASE_URL` to the deployed backend API URL.

## Getting Started

```bash
npm install
npm run dev
```

The local development app runs on:

```text
http://localhost:5173
```

## Production Build

```bash
npm run build
npm run preview
```

## Quality Checks

```bash
npm run typecheck
npm run lint
npm run build
```

## Main Screens

- Public landing pages
- Login and signup
- Dashboard overview
- Markets and heatmap
- Stocks and stock detail
- Sectors and sector detail
- AI insights
- Portfolio
- Watchlists
- Alerts
- Profile and settings
- Admin overview, users, and activity

## Backend Integration

The frontend reads its API base URL from `VITE_API_BASE_URL` and calls the backend services for market data, model status, predictions, insights, portfolio, watchlist, alert, auth, and admin flows.

Mock mode should stay disabled for production demos:

```env
VITE_USE_MOCK=false
```

## Demo Startup

Start the backend first:

```bash
uvicorn app.main:app --reload --port 8000
```

Then start the frontend:

```bash
npm run dev
```

Open:

```text
http://localhost:5173
```

Recommended demo path:

1. Open the dashboard and confirm market data loads.
2. Show model/engine status if exposed in the UI.
3. Open Markets to show the heatmap.
4. Open a stock detail page.
5. Run or show a prediction/recommendation result.
6. Explain that XGBoost is the production model and LSTM is optional.

## Security Notes

- Do not commit `.env`.
- Do not expose backend secrets in frontend environment variables.
- Only use public frontend configuration values prefixed with `VITE_`.

