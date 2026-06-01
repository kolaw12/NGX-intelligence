export const ROUTES = {
  // Public
  home: "/",
  features: "/features",
  about: "/about",
  contact: "/contact",
  login: "/login",
  signup: "/signup",
  forgotPassword: "/forgot-password",

  // App (protected)
  app: "/app",
  dashboard: "/app",
  markets: "/app/markets",
  sectors: "/app/sectors",
  sectorDetail: (slug: string) => `/app/sectors/${slug}`,
  stocks: "/app/stocks",
  stockDetail: (symbol: string) => `/app/stocks/${symbol}`,
  aiInsights: "/app/ai-insights",
  portfolio: "/app/portfolio",
  watchlists: "/app/watchlists",
  alerts: "/app/alerts",
  settings: "/app/settings",
  profile: "/app/profile",

  // Admin portal (admin only)
  admin: "/admin",
  adminOverview: "/admin",
  adminUsers: "/admin/users",
  adminActivity: "/admin/activity",
  adminUserDetail: (id: string) => `/admin/users/${id}`,
} as const;

export const PUBLIC_ROUTES = [
  ROUTES.home,
  ROUTES.features,
  ROUTES.about,
  ROUTES.contact,
];

export const AUTH_ROUTES = [ROUTES.login, ROUTES.signup, ROUTES.forgotPassword];
