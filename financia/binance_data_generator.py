"""
Binance Data Generator

Generates training data for crypto trading from Binance.
Uses ccxt library for data fetching.

Timeframes (Crypto trades faster than stocks):
- short: 1m (scalping/ultra-fast) - vs BIST100 1h
- mid: 15m (day trading) - vs BIST100 4h
- long: 4h (swing trading) - vs BIST100 1d
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from tqdm import tqdm
import os

from financia.indicator_config import get_interval, get_data_period, get_config

# Top 20 Coins by Market Cap (excluding stablecoins)
BINANCE_COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "UNIUSDT", "ATOMUSDT", "LTCUSDT", "ETCUSDT",
    "NEARUSDT", "APTUSDT", "FILUSDT", "ARBUSDT", "OPUSDT"
]

def fetch_binance_data(symbol: str, interval: str = '1m', days: int = 7):
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
    
    print(f"  Fetching {symbol} ({interval}, {days} days)...")
    
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
    
    print(f"  Fetched {len(df)} candles for {symbol}")
    
    return df


class BinanceAnalyzer:
    """
    Analyzer for Binance crypto data.
    Uses market-specific indicator configurations.
    """
    
    def __init__(self, symbol: str, horizon: str = 'short', days: int = None):
        """
        Initialize BinanceAnalyzer.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            horizon: 'short' (1m), 'mid' (15m), 'long' (4h)
            days: Override default days to fetch
        """
        self.symbol = symbol
        self.ticker = symbol  # Compatibility with RL code
        self.horizon = horizon.lower()
        self.market = 'binance'
        
        # Get config from indicator_config module
        interval = get_interval('binance', self.horizon)
        default_days = get_data_period('binance', self.horizon)
        
        fetch_days = days if days else default_days
        
        self.data = fetch_binance_data(symbol, interval, fetch_days)
        self.config = get_config('binance', self.horizon)
        
    def prepare_rl_features(self):
        """
        Generate features for RL training.
        Uses the same indicator logic as StockAnalyzer but with Binance-specific config.
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
        temp.market = 'binance'  # Mark as binance for config selection
        
        # Use the same feature preparation
        return temp.prepare_rl_features()


def generate_binance_dataset(horizon: str, output_file: str, days: int = None):
    """
    Generate dataset for Binance coins.
    """
    interval = get_interval('binance', horizon)
    default_days = get_data_period('binance', horizon)
    fetch_days = days if days else default_days
    
    print(f"\n{'='*60}")
    print(f"Generating Binance Dataset: {horizon.upper()}")
    print(f"Interval: {interval}")
    print(f"Days: {fetch_days}")
    print(f"Target File: {output_file}")
    print(f"Coins: {len(BINANCE_COINS)}")
    print(f"{'='*60}")
    
    all_data = []
    
    for symbol in tqdm(BINANCE_COINS, desc=f"Processing {horizon}"):
        try:
            analyzer = BinanceAnalyzer(symbol, horizon=horizon, days=fetch_days)
            
            if analyzer.data is None or len(analyzer.data) < 200:
                print(f"Skipping {symbol}: Not enough data ({len(analyzer.data) if analyzer.data is not None else 0} candles).")
                continue
            
            df_features = analyzer.prepare_rl_features()
            
            if df_features.empty:
                print(f"Skipping {symbol}: Feature generation failed.")
                continue
                
            df_features['Ticker'] = symbol
            df_features.reset_index(inplace=True)
            
            all_data.append(df_features)
            
            time.sleep(0.3)  # Rate limiting
            
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    if not all_data:
        print("No data collected.")
        return
    
    final_df = pd.concat(all_data, ignore_index=True)
    
    # Ensure directories exist
    update_dir = os.path.dirname(output_file)
    if update_dir:
        os.makedirs(update_dir, exist_ok=True)
        os.makedirs(f"{update_dir}/updates", exist_ok=True)
    
    final_df.to_parquet(output_file, index=False)
    print(f"\n✅ Saved {len(final_df)} rows to {output_file}")
    print(f"   Coins processed: {final_df['Ticker'].nunique()}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate Binance Training Dataset")
    parser.add_argument("--horizon", type=str, default="all", choices=["short", "mid", "long", "all"],
                        help="Which horizon to generate (default: all)")
    args = parser.parse_args()
    
    data_dir = "binance_data"
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(f"{data_dir}/updates", exist_ok=True)
    
    horizons_to_generate = []
    
    if args.horizon == "all":
        horizons_to_generate = ["short", "mid", "long"]
    else:
        horizons_to_generate = [args.horizon]
    
    for horizon in horizons_to_generate:
        output_file = f'{data_dir}/binance_dataset_{horizon}.parquet'
        generate_binance_dataset(horizon, output_file)
    
    print("\n" + "="*60)
    print("✅ Binance Data Generation Complete!")
    print("="*60)

