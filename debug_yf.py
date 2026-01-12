import yfinance as yf
import pandas as pd

ticker = "ENKAI.IS"
print(f"Downloading {ticker}...")
try:
    data = yf.download(ticker, period="1mo", interval="1d")
    print("Download finished.")
    print(f"Data shape: {data.shape}")
    print(data.head())
    if data.empty:
        print("Data is empty!")
    else:
        print("Columns:", data.columns)
except Exception as e:
    print(f"Error: {e}")
