import pandas as pd
from pathlib import Path

tickers = pd.read_csv('data/master/tickers.csv')
print(tickers.columns.tolist())
print(tickers[tickers['name'].str.contains('Tatum', case=False, na=False)])
