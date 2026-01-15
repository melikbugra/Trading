"""
Binance Data Generator

Generates training data for crypto trading from Binance.
Uses ccxt library for data fetching.

Timeframes (Crypto trades faster):
- short: 5m (vs BIST100 1h)
- mid: 1h (vs BIST100 4h)  
- long: 4h (vs BIST100 1d)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from tqdm import tqdm
import os

# Top 20 Coins by Market Cap (excluding stablecoins)
BINANCE_COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "UNIUSDT", "ATOMUSDT", "LTCUSDT", "ETCUSDT",
    "NEARUSDT", "APTUSDT", "FILUSDT", "ARBUSDT", "OPUSDT"
]

def fetch_binance_data(symbol: str, interval: str = '5m', days: int = 30):
    """
    Fetch OHLCV data from Binance using ccxt.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Candle interval ('1m', '5m', '15m', '1h', '4h', '1d')
        days: Number of days of history to fetch
    """
    try:
        import ccxt
    except ImportError:
        print("ccxt not installed. Run: pip install ccxt")
        return None
    
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })
    
    # Calculate start time
    since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    all_ohlcv = []
    
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, interval, since=since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1  # Next batch starts after last candle
            
            # Check if we've caught up to now
            if ohlcv[-1][0] >= int(datetime.now().timestamp() * 1000) - 60000:
                break
                
            time.sleep(0.1)  # Rate limiting
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            break
    
    if not all_ohlcv:
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(all_ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['Datetime'] = pd.to_datetime(df['Timestamp'], unit='ms')
    df.set_index('Datetime', inplace=True)
    df.drop('Timestamp', axis=1, inplace=True)
    
    return df


class BinanceAnalyzer:
    """
    Analyzer for Binance crypto data.
    Similar to StockAnalyzer but with crypto-specific timeframes.
    """
    
    def __init__(self, symbol: str, horizon: str = 'short', days: int = None):
        """
        Initialize BinanceAnalyzer.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            horizon: 'short' (5m), 'mid' (1h), 'long' (4h)
            days: Override default days to fetch
        """
        self.symbol = symbol
        self.ticker = symbol  # Compatibility with RL code
        self.horizon = horizon.lower()
        
        # Configure based on horizon (Crypto-optimized)
        if self.horizon == 'short':
            interval = '5m'
            default_days = 60  # ~17k candles
        elif self.horizon == 'mid' or self.horizon == 'short-mid':
            interval = '1h'
            default_days = 365  # ~8.7k candles
        else:  # long
            interval = '4h'
            default_days = 730  # ~4.4k candles
            
        fetch_days = days if days else default_days
        
        self.data = fetch_binance_data(symbol, interval, fetch_days)
        
    def prepare_rl_features(self):
        """
        Generate features for RL training.
        Uses the same indicator logic as StockAnalyzer.
        """
        if self.data is None or self.data.empty:
            return pd.DataFrame()
        
        # Import the indicator calculations from main analyzer
        from financia.analyzer import StockAnalyzer
        
        # Create a temporary StockAnalyzer-like object to reuse indicator logic
        temp = StockAnalyzer.__new__(StockAnalyzer)
        temp.ticker = self.symbol
        temp.horizon = self.horizon
        temp.data = self.data.copy()
        
        # Use the same feature preparation
        return temp.prepare_rl_features()


def generate_binance_dataset(horizon: str, output_file: str, days: int = None):
    """
    Generate dataset for Binance coins.
    """
    print(f"\nGenerating Binance Dataset: {horizon.upper()}")
    print(f"Target File: {output_file}")
    print(f"Coins: {len(BINANCE_COINS)}")
    
    all_data = []
    
    for symbol in tqdm(BINANCE_COINS):
        try:
            analyzer = BinanceAnalyzer(symbol, horizon=horizon, days=days)
            
            if analyzer.data is None or len(analyzer.data) < 200:
                print(f"Skipping {symbol}: Not enough data.")
                continue
            
            df_features = analyzer.prepare_rl_features()
            df_features['Ticker'] = symbol
            df_features.reset_index(inplace=True)
            
            all_data.append(df_features)
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
    
    if not all_data:
        print("No data collected.")
        return
    
    final_df = pd.concat(all_data, ignore_index=True)
    
    # Ensure updates directory exists
    update_dir = os.path.dirname(output_file)
    os.makedirs(update_dir, exist_ok=True)
    os.makedirs(f"{update_dir}/updates", exist_ok=True)
    
    final_df.to_parquet(output_file, index=False)
    print(f"Saved {len(final_df)} rows to {output_file}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate Binance Training Dataset")
    args = parser.parse_args()
    
    data_dir = "binance_data"
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(f"{data_dir}/updates", exist_ok=True)
    
    # 1. Short Term (5-minute - 60 days)
    generate_binance_dataset('short', f'{data_dir}/binance_dataset_short.parquet', days=60)
    
    # 2. Mid Term (1-hour - 1 year)
    generate_binance_dataset('mid', f'{data_dir}/binance_dataset_mid.parquet', days=365)
    
    # 3. Long Term (4-hour - 2 years)
    generate_binance_dataset('long', f'{data_dir}/binance_dataset_long.parquet', days=730)
