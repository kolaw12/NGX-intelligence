# NGX Intelligence Frontend Deployment

Recommended host: Vercel.

## Required setting

Set this environment variable in the hosting dashboard:

```bash
VITE_API_BASE_URL=https://YOUR_BACKEND_URL/api/v1
VITE_USE_MOCK=false
```

## Build settings

```bash
Install command: npm ci
Build command: npm run build
Output directory: dist
```

`vercel.json` already handles React Router page refreshes by routing app paths
back to `index.html`.

## After deployment

1. Open the frontend URL.
2. Confirm the dashboard loads.
3. Confirm stock detail pages work after browser refresh.
4. Confirm network calls go to the deployed backend, not localhost.
