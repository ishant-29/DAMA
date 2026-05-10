
import yfinance as yf

symbol = "HGINFRA.NS"
print(f"Fetching data for {symbol}...")
data = yf.download(symbol, period="1y", interval="1d", auto_adjust=True)
if data.empty:
    print(f"No data found for {symbol}.")
else:
    print(f"Data found for {symbol}:")
    print(data.head())
