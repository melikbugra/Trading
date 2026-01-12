import argparse
import pandas as pd
import numpy as np
from rl_baselines.policy_based.ppo import PPO
from financia.envs.trading_env import TradingEnv
from financia.analyzer import StockAnalyzer
import sys
import os
import financia.envs # Register env
from types import SimpleNamespace
import torch

class InferenceEngine:
    def __init__(self, model_path):
        self.model_path = model_path
        if not self.model_path.endswith(".ckpt"):
            self.model_path += ".ckpt"
            
        self.model = None
        self.device = 'cpu'
        
    def get_dummy_env(self):
        # Try to load from parquet to get correct shape
        parquet_path = "data/dataset_short_mid.parquet"
        if os.path.exists(parquet_path):
            df = pd.read_parquet(parquet_path).head(100)
        else:
            # Fallback: Fetch live one just for shape
            print("Dataset not found, fetching live sample for shape...")
            analyzer = StockAnalyzer("THYAO.IS", horizon="short-mid")
            df = analyzer.prepare_rl_features().head(100)
            
        env = TradingEnv(df)
        env.spec = SimpleNamespace(id="TradingEnv-v0")
        return env

    def load_model(self):
        if not os.path.exists(self.model_path):
            print(f"Error: Model not found at {self.model_path}")
            return False

        try:
            env = self.get_dummy_env()
            
            # Initialize PPO with explicit network_type (must match training)
            # Assuming 'mlp' as per train.py
            self.model = PPO(
                env=env,
                network_type="mlp", 
                device=self.device
            )
            
            self.model.load(self.model_path)
            print(f"Model loaded from {self.model_path}")
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False

    def analyze_ticker(self, ticker, horizon='short'):
        if self.model is None:
            if not self.load_model():
               return {"error": "Model failed to load"}
            
        try:
            analyzer = StockAnalyzer(ticker, horizon=horizon)
            if analyzer.data is None or analyzer.data.empty:
                return {"error": "No data found"}
                
            df = analyzer.prepare_rl_features()
            if df.empty:
                 return {"error": "Not enough data"}
            
            # Feature Columns Logic
            exclude_cols = ['Date', 'Ticker', 'Timestamp', 'index', 'Close', 'Datetime']
            feature_cols = [c for c in df.columns if c not in exclude_cols]
            
            last_obs = df.iloc[-1][feature_cols].values.astype(np.float32)
            
            # Account State (Neutral)
            account_obs = np.array([0.0, 0.0, 0.0], dtype=np.float32)
            final_obs = np.concatenate([last_obs, account_obs])
            
            # Predict using rl_baselines API
            # Need to convert state to tensor
            # BaseAlgorithm.state_to_torch handles unsqueeze(0)
            state_tensor = self.model.state_to_torch(final_obs)
            
            action_tensor = self.model.agent.select_greedy_action(state_tensor, eval=True)
            
            if self.model.agent.action_type == "discrete":
                action = action_tensor.item()
            else:
                action = action_tensor.item() # Wrapper usually handles this, assuming Discrete(3)
            
            action_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
            decision = action_map.get(int(action), "UNKNOWN")
            
            # Perform Full Technical Analysis for UI Details
            indicators = ["RSI", "MACD", "BB", "MA", "DMI", "SAR", "STOCH", "STOCHRSI", "SUPERTREND", "ICHIMOKU", "ALLIGATOR", "AWESOME", "MFI", "CMF", "WAVETREND", "KAMA", "GATOR", "DEMAND_INDEX", "WILLIAMS_R", "AROON", "DEMA", "MEDIAN", "FISHER"]
            
            df_decisions = analyzer.get_indicator_decisions(*indicators)
            score, category_scores = analyzer.calculate_final_score(df_decisions)
            
            # Volume Ratio Calculation
            vol = analyzer.data['Volume']
            vol_ma = vol.rolling(window=20).mean()
            vol_ratio = 0.0
            if len(vol) >= 20 and vol_ma.iloc[-1] > 0:
                vol_ratio = float(vol.iloc[-1] / vol_ma.iloc[-1])
            
            # Convert DataFrame to list of dicts for JSON
            # Handle NaN values for JSON safety
            details_list = df_decisions.replace({np.nan: None}).to_dict(orient='records')
            
            return {
                "decision": decision,
                "action_code": int(action),
                "price": float(analyzer.data['Close'].iloc[-1]),
                "volume": float(analyzer.data['Volume'].iloc[-1]),
                "volume_ratio": vol_ratio,
                "timestamp": str(df.index[-1]),
                # New Fields
                "final_score": float(score),
                "category_scores": category_scores,
                "indicator_details": details_list
            }
            
        except Exception as e:
            return {"error": str(e)}

# CLI Wrapper using the Class
def get_decision(model_path, ticker, horizon):
    engine = InferenceEngine(model_path)
    result = engine.analyze_ticker(ticker, horizon)
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return

    print("\n" + "="*30)
    print(f"ANALYSIS: {ticker}")
    print(f"Horizon: {horizon}")
    print(f"Latest Date: {result['timestamp']}")
    print(f"Close Price: {result['price']:.2f}")
    print("-" * 30)
    print(f"Model Decision: {result['decision']} ({result['action_code']})")
    print("="*30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get RL Model Decision for a Ticker")
    parser.add_argument("model_path", type=str, help="Path to the trained model")
    parser.add_argument("ticker", type=str, help="Stock Ticker (e.g., THYAO.IS)")
    parser.add_argument("--horizon", type=str, default="short", choices=["short", "medium", "long", "short-mid"], help="Trading Horizon")
    
    args = parser.parse_args()
    get_decision(args.model_path, args.ticker, args.horizon)
