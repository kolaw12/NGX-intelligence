export const qk = {
  // Stocks
  stocks: ["stocks"] as const,
  stock: (symbol: string) => ["stock", symbol] as const,
  stockChart: (symbol: string, range: string) => ["stock", symbol, "chart", range] as const,
  stocksBySector: (slug: string) => ["stocks", "sector", slug] as const,

  // Sectors
  sectors: ["sectors"] as const,
  sector: (slug: string) => ["sector", slug] as const,

  // Markets
  marketOverview: ["market", "overview"] as const,
  topMovers: ["market", "top-movers"] as const,

  // Macro
  macroIndicators: ["macro", "indicators"] as const,
  macroEvents: ["macro", "events"] as const,

  // AI
  marketSentiment: ["ai", "sentiment"] as const,
  aiInsight: (symbol: string) => ["ai", "insight", symbol] as const,
  aiInsights: ["ai", "insights"] as const,

  // Portfolio
  portfolio: ["portfolio"] as const,

  // Watchlist
  watchlists: ["watchlists"] as const,

  // Alerts
  alerts: ["alerts"] as const,

  // News
  news: (symbol?: string) => (symbol ? (["news", symbol] as const) : (["news"] as const)),

  // Auth
  me: ["auth", "me"] as const,
} as const;
