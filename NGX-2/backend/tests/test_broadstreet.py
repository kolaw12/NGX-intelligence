from data.fetchers.broadstreet import BroadStreetFetcher

MARKET_URL = "https://broadstreetlagos.com/exchange-rate.php"

fetcher = BroadStreetFetcher()

# Step 1 — Login
fetcher.login()

# Step 2 — Fetch protected page
html = fetcher.fetch_market_page(MARKET_URL)

# Step 3 — Parse exchange rate table
exchange_df = fetcher.get_exchange_rate_table(html)

# Step 4 — Preview extracted dataframe
print("\nEXCHANGE RATE DATAFRAME:\n")

print(exchange_df.head())