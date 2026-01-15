import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from rl_baselines.policy_based.ppo import PPO
from financia.envs.trading_env import TradingEnv
import os
from types import SimpleNamespace
import torch

def evaluate_agent(dataset_path, model_path, initial_balance=10000, random_mode=False):
    print(f"Loading data from {dataset_path}...")
    df = pd.read_parquet(dataset_path)
    
    # Use Validation Split (Last 20%)
    split_idx = int(len(df) * 0.8)
    val_df = df.iloc[split_idx:].reset_index(drop=True)
    
    print(f"Evaluating on {len(val_df)} bars (Validation Set).")
    
    # Create Environment
    # Increase max_steps to see more trading activity over longer period
    env = TradingEnv(val_df, initial_balance=initial_balance, max_steps=5000)
    # Patch spec
    env.spec = SimpleNamespace(id="TradingEnv-v0")
    
    if not random_mode:
        # Load Model
        # model_path might be missing extension if passed from CLI default
        if not model_path.endswith(".ckpt"):
            model_path += ".ckpt"
            
        print(f"Loading model from {model_path}...")
        
        # Init PPO instance
        model = PPO(
            env=env,
            network_type="mlp",
            device='cpu'
        )
        model.load(model_path)
    else:
        print("Running in RANDOM MODE (No model loaded)")
    
    # Run Simulation
    obs, _ = env.reset()
    done = False
    
    net_worths = []
    actions = []
    
    print("Running backtest...")
    obs, _ = env.reset()
    
    steps = 0
    while not done:
        if random_mode:
             action = env.action_space.sample()
        else:
            # Convert obs to tensor for PPO
            obs_tensor = model.state_to_torch(obs)
            action_tensor = model.agent.select_greedy_action(obs_tensor, eval=True)
            
            if model.agent.action_type == "discrete":
                action = action_tensor.item()
            else:
                action = action_tensor.item()
            
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        
        net_worths.append(info['net_worth'])
        actions.append(action)
        steps += 1
        
    print(f"Total Steps: {steps}")
    
    # Metrics
    initial_balance = env.initial_balance
    final_balance = env.net_worth
    net_profit = final_balance - initial_balance
    roi = (net_profit / initial_balance) * 100
    
    # Calculate Max Drawdown
    net_worth_series = pd.Series(net_worths)
    running_max = net_worth_series.cummax()
    drawdown = (net_worth_series - running_max) / running_max
    max_drawdown = drawdown.min() * 100
    
    # Trade Stats
    trades = env.trades
    total_executions = len(trades)
    
    wins = 0
    losses = 0
    
    # reconstruct roundtrips
    entry_price = 0
    in_position = False
    
    for trade in trades:
        if trade['type'] == 'buy':
            if not in_position:
                entry_price = trade['price']
                in_position = True
        elif trade['type'] == 'sell':
            if in_position:
                exit_price = trade['price']
                if exit_price > entry_price:
                    wins += 1
                else:
                    losses += 1
                in_position = False
                
    completed_roundtrips = wins + losses
    win_rate = (wins / completed_roundtrips * 100) if completed_roundtrips > 0 else 0
    
    print("\n" + "="*30)
    print("       EVALUATION RESULTS       ")
    print("="*30)
    print(f"Initial Balance: ₺{initial_balance:,.2f}")
    print(f"Final Balance:   ₺{final_balance:,.2f}")
    print(f"Net Profit:      ₺{net_profit:,.2f}")
    print(f"ROI:             {roi:.2f}%")
    print(f"Max Drawdown:    {max_drawdown:.2f}%")
    print("-" * 30)
    print(f"Total Executions:{total_executions}")
    print(f"Completed Trips: {completed_roundtrips}")
    print(f"Win Rate:        {win_rate:.2f}% ({wins} W / {losses} L)")
    print("="*30)
    
    # Breakdown by Ticker
    print("\n" + "="*30)
    print("       PERFORMANCE BY TICKER    ")
    print("="*30)
    
    ticker_stats = {}
    
    # Map trades to tickers
    # trades list has: {'step': ..., 'type': ..., 'price': ...}
    # env.tickers array maps step -> ticker
    
    # We need to match buys and sells
    # Since env logic forces sell on ticker change, we can assume FIFO or just track pnl per trade
    
    # Re-iterate to calculate PnL per ticker
    current_position = None # {ticker, entry_price, shares} - simplified model in env just holds 'shares'
    # But environment handles one ticker at a time mostly? 
    # Actually env iterates sequentially. If multiple tickers exist, they differ by step.
    
    # Let's simple traverse trades
    trade_log = []
    
    # We need to track open position manualy to match with tickers
    # Env 'trades' doesn't store ticker, so we lookup
    
    open_trade = None
    
    for t in trades:
        step = t['step']
        ticker = env.tickers[step]
        price = t['price']
        action_type = t['type']
        
        if ticker not in ticker_stats:
            ticker_stats[ticker] = {'wins': 0, 'losses': 0, 'pnl': 0.0, 'trades': 0}
            
        if action_type == 'buy':
            if open_trade is None:
                open_trade = {'ticker': ticker, 'entry': price}
        
        elif action_type == 'sell':
            if open_trade:
                # Check if same ticker (should be, barring data jumps)
                if open_trade['ticker'] == ticker:
                    pnl = (price - open_trade['entry']) / open_trade['entry']
                    ticker_stats[ticker]['pnl'] += pnl
                    ticker_stats[ticker]['trades'] += 1
                    
                    if pnl > 0:
                        ticker_stats[ticker]['wins'] += 1
                    else:
                        ticker_stats[ticker]['losses'] += 1
                
                open_trade = None
                
    # Print Stats
    print(f"{'TICKER':<10} | {'TRADES':<6} | {'WIN RATE':<9} | {'TOT. RETURN (Sum%)':<15}")
    print("-" * 50)
    
    sorted_tickers = sorted(ticker_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)
    
    for ticker, stats in sorted_tickers:
        total = stats['trades']
        if total > 0:
            wr = (stats['wins'] / total) * 100
            print(f"{ticker:<10} | {total:<6} | {wr:6.1f}%   | {stats['pnl']*100:>.2f}%")
            
    print("="*30)

    # Plotting
    plt.figure(figsize=(12, 6))
    plt.plot(net_worths, label='Equity Curve')
    title_suffix = " (RANDOM)" if random_mode else f": {model_path}"
    plt.title(f'Backtest Results{title_suffix}')
    plt.xlabel('Steps')
    plt.ylabel('Net Worth')
    plt.legend()
    plt.grid(True)
    
    # Save Plot
    os.makedirs("results", exist_ok=True)
    plot_path = "results/evaluation_plot.png"
    plt.savefig(plot_path)
    print(f"\nPlot saved to {plot_path}")

import argparse
from financia.analyzer import StockAnalyzer
from datetime import datetime, timedelta

def calculate_oracle_profit(prices, initial_balance=10000, fee=0.001):
    """
    Calculates the theoretical maximum profit using Dynamic Programming.
    States: 0=Cash, 1=Held
    """
    cash = initial_balance
    shares = 0
    
    # DP States
    # dp_cash[t] = max cash at time t
    # dp_shares[t] = max shares at time t
    
    # Vectorized approach is hard due to path dependency.
    # Fast loop is fine for <100k points.
    
    # Actually, greedy strategy works for strictly positive fee?
    # "Buy if price will go up enough to cover fee"
    # The optimal strategy is to hold whenever price is rising and cash whenever falling.
    # We just need to handle the fee threshold.
    # Standard DP:
    # State 0 (Cash): max(Stay Cash, Sell Shares) -> Wait, we don't have shares in State 0.
    # We have previous states.
    
    # cash[t] = max(cash[t-1], shares[t-1] * p[t] * (1-fee))
    # shares[t] = max(shares[t-1], cash[t-1] / p[t] * (1-fee))  <- (1-fee) because buying reduces purchasing power
    
    n = len(prices)
    if n == 0: return initial_balance
    
    dp_cash = np.zeros(n)
    dp_shares = np.zeros(n)
    
    dp_cash[0] = initial_balance
    dp_shares[0] = initial_balance / prices[0] * (1 - fee)
    
    for i in range(1, n):
        curr_price = prices[i]
        
        # Option 1: To have CASH at i
        # - We had CASH at i-1 and kept it.
        # - We had SHARES at i-1 and SOLD them.
        dp_cash[i] = max(dp_cash[i-1], dp_shares[i-1] * curr_price * (1 - fee))
        
        # Option 2: To have SHARES at i
        # - We had SHARES at i-1 and kept them.
        # - We had CASH at i-1 and BOUGHT shares.
        dp_shares[i] = max(dp_shares[i-1], dp_cash[i-1] / curr_price * (1 - fee))
        
    return dp_cash[-1]

def evaluate_specific_ticker(ticker, days, model_path, initial_balance=10000, random_mode=False, oracle_mode=False, live_mode=False):
    print(f"\n--- Specific Ticker Evaluation: {ticker} (Last {days} days) ---")
    
    # 1. Fetch Data & Generate Features (reuse logic from DataGenerator)
    # We fetch 2 years to ensure indicators (SMA200 etc) are warm, then slice.
    print(f"Fetching data for {ticker}...")
    try:
        analyzer = StockAnalyzer(ticker, horizon='short-mid', period='2y')
        if analyzer.data is None or len(analyzer.data) < 200:
            print(f"Error: Not enough data for {ticker}")
            return
        # Drop last candle for stable signals (unless live_mode)
        if not live_mode and len(analyzer.data) > 1:
            analyzer.data = analyzer.data.iloc[:-1]
            print("Using STABLE mode (Closed candles only)")
        else:
            print("Using LIVE mode (Including developing candle)")

        df = analyzer.prepare_rl_features()
        
        # Add Ticker column (required by TradingEnv)
        df['Ticker'] = ticker
        
        # Filter for requested duration
        # Assuming index is Datetime
        cutoff_date = df.index.max() - timedelta(days=days)
        df = df[df.index >= cutoff_date]
        
        if len(df) == 0:
            print(f"Error: No data found for the last {days} days.")
            return

        print(f"Data ready: {len(df)} bars from {df.index.min()} to {df.index.max()}")
        
        # Reset index to make it integer-based for Environment compatibility
        df = df.reset_index()
        
    except Exception as e:
        print(f"Error preparing data: {e}")
        return

    # 2. Run Evaluation
    # Create Environment
    # max_steps must be at least length of df to encompass full range
    env = TradingEnv(df, initial_balance=initial_balance, max_steps=len(df)+100)
    env.spec = SimpleNamespace(id="TradingEnv-v0")
    
    # Load Model
    model = None
    if not random_mode and not oracle_mode:
        if not model_path.endswith(".ckpt"):
            model_path += ".ckpt"
            
        print(f"Loading model from {model_path}...")
        try:
            model = PPO(env=env, network_type="mlp", device='cpu')
            model.load(model_path)
        except Exception as e:
            print(f"Error loading model: {e}")
            return
    elif random_mode:
        print("Running in RANDOM MODE")
    elif oracle_mode:
        print("Running in ORACLE MODE (Max Potential Calculation)")

    # Run Simulation
    print("Running simulation...")
    obs, _ = env.reset(options={'start_step': 0}) # Force start at 0
    done = False
    
    net_worths = []
    
    while not done:
        if oracle_mode:
             # Just run creating random actions just to step through env?
             # Or better: Just calculate oracle profit on the DF directly and skip simulation.
             # Env requires actions.
             # Let's just break here if oracle mode, calculate and print.
             break
        
        if random_mode:
            action = env.action_space.sample()
        else:
            obs_tensor = model.state_to_torch(obs)
            action_tensor = model.agent.select_greedy_action(obs_tensor, eval=True)
            action = action_tensor.item()
            
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        
        net_worths.append(info['net_worth'])
        
    # Report Results
    if not oracle_mode:
        initial = env.initial_balance
        final = env.net_worth
        profit = final - initial
        roi = (profit / initial) * 100
        
        print("\n" + "="*40)
        print(f" RESULTS FOR {ticker} (Last {days} Days)")
        print("="*40)
        print(f"Initial: ₺{initial:,.2f}")
        print(f"Final:   ₺{final:,.2f}")
        print(f"Profit:  ₺{profit:,.2f}")
        print(f"ROI:     {roi:.2f}%")
        
        # Trades Summary
        trades = env.trades
        total_trades = len(trades) // 2 # Rough estimate of round trips
        print(f"Trades:  {len(trades)} executions")
        
        # Detailed Trade Log
        if len(trades) > 0:
            print("\n" + "="*44)
            print(f" {'DATE / TIME':<22} | {'TYPE':<6} | {'PRICE':<10}")
            print("-" * 44)
            
            # Identify Date Column
            date_col = 'index'
            if 'Date' in df.columns: date_col = 'Date'
            elif 'Datetime' in df.columns: date_col = 'Datetime'
            
            for t in trades:
                step = t['step']
                price = t['price']
                action = t['type'].upper() # buy/sell
                
                # Get Date from DataFrame
                # step corresponds to df index after reset_index
                date_str = str(df.iloc[step][date_col])
                
                print(f" {date_str:<22} | {action:<6} | ₺{price:<9.2f}")
                
        print("="*40)
    
    # Oracle Benchmark
    if oracle_mode:
        prices = df['Close'].values
        # Need to re-calculate if the earlier simulation was skipped
        # But simulation logic loop skipped, so 'prices' is safe.
        max_possible = calculate_oracle_profit(prices, initial_balance)
        
        profit_oracle = max_possible - initial_balance
        roi_oracle = (profit_oracle / initial_balance) * 100
        
        print(f"\n[ORACLE BENCHMARK - MAXIMUM THEORETICAL PROFIT]")
        print(f"Max Possible: ₺{max_possible:,.2f}")
        print(f"Max Profit:   ₺{profit_oracle:,.2f}")
        print(f"Max ROI:      {roi_oracle:.2f}%")
        print("="*40)
    
    # Plot
    plt.figure(figsize=(10, 5))
    plt.plot(net_worths, label=f'{ticker} Equity')
    title_suffix = " (RANDOM)" if random_mode else ""
    plt.title(f'Evaluation: {ticker} (Last {days} Days){title_suffix}')
    plt.xlabel('Steps (4H Bars)')
    plt.ylabel('Net Worth')
    plt.legend()
    plt.grid(True)
    
    os.makedirs("results", exist_ok=True)
    plot_path = f"results/eval_{ticker}_{days}d.png"
    plt.savefig(plot_path)
    print(f"Plot saved to {plot_path}")


def backtest_production_simulation(ticker, model_path, initial_balance=10000, random_mode=False, live_mode=False):
    mode_label = "LIVE (Developing Candle)" if live_mode else "STABLE (Closed Candles)"
    print(f"\n--- Production Simulation: {ticker} (Last 5 Days / 1m Resolution / 15m Latency) [{mode_label}] ---")
    
    # 1. Fetch 1M Data (Execution Data)
    print("Fetching 1m Execution Data (Max 7 days)...")
    analyzer_1m = StockAnalyzer(ticker, horizon='short', period='7d', interval='1m')
    if analyzer_1m.data is None or analyzer_1m.data.empty:
        print("Error: Could not fetch 1m data.")
        return
    
    df_exec = analyzer_1m.data
    # Determine simulation start/end from 1m data
    sim_start = df_exec.index.min()
    sim_end = df_exec.index.max()
    print(f"Execution Data: {len(df_exec)} bars from {sim_start} to {sim_end}")
    
    # 2. Fetch 1H Data (Signal Data)
    # We need enough history for indicators, but covering the simulation period
    print("Fetching 1h Signal Data (2 Years for Indicator Warmup)...")
    analyzer_1h = StockAnalyzer(ticker, horizon='short', period='730d', interval='1h')
    
    # 3. Prepare Model
    if not random_mode:
        if not model_path.endswith(".ckpt"): model_path += ".ckpt"
        print(f"Loading Model: {model_path}")
        
        # We need a dummy env to load the model architecture
        dummy_df = analyzer_1h.prepare_rl_features().head(100)
        dummy_df['Ticker'] = ticker
        dummy_env = TradingEnv(dummy_df)
        dummy_env.spec = SimpleNamespace(id="TradingEnv-v0")
        
        try:
            model = PPO(env=dummy_env, network_type="mlp", device='cpu')
            model.load(model_path)
        except Exception as e:
            print(f"Error loading model: {e}")
            return
    else:
        print("Running in RANDOM MODE")
        model = None

    # 4. Generate All Decision Signals
    signal_cache = {} # Timestamp -> Action Code
    
    if not live_mode:
        # STABLE MODE: Generate signals only at hourly boundaries (closed candles)
        print("Generating Signals on 1h Data (Stable Mode)...")
        df_signals = analyzer_1h.prepare_rl_features()
        feature_cols = [c for c in df_signals.columns if c not in ['Date', 'Ticker', 'Timestamp', 'Close']]
        relevant_signals = df_signals[df_signals.index >= (sim_start - timedelta(days=1))]
        
        print(f"Processing {len(relevant_signals)} hourly candles for signals...")
        
        for idx, row in relevant_signals.iterrows():
            if random_mode:
                action = np.random.randint(0, 3)
            else:
                obs = row[feature_cols].values.astype(np.float32)
                account_obs = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                final_obs = np.concatenate([obs, account_obs])
                obs_tensor = model.state_to_torch(final_obs)
                action_tensor = model.agent.select_greedy_action(obs_tensor, eval=True)
                action = action_tensor.item()
            
            # Signal valid 1h + 15m after candle OPEN
            signal_valid_from = idx + timedelta(hours=1, minutes=15)
            signal_cache[signal_valid_from] = action
    else:
        # LIVE MODE: Generate signals every 15 minutes using developing candle
        print("Generating Signals with Developing Candle (Live Mode)...")
        print("This simulates real-time decision making with partial hourly data...")
        
        # Get closed hourly candles (all except the absolute last one)
        df_1h_base = analyzer_1h.data.iloc[:-1].copy()
        
        # Generate signal time points (every 15 minutes during market hours)
        signal_times = pd.date_range(
            start=sim_start.replace(minute=0, second=0),
            end=sim_end,
            freq='15min'
        )
        
        # Filter to market hours only (09:00 - 18:00 Turkish time)
        signal_times = [t for t in signal_times if 9 <= t.hour < 18]
        
        print(f"Processing {len(signal_times)} signal points (every 15 min)...")
        
        for sig_time in signal_times:
            # Get the hour boundary for this signal time
            hour_start = sig_time.replace(minute=0, second=0, microsecond=0)
            
            # Get 1m data for the developing candle (from hour_start to sig_time)
            developing_1m = df_exec[(df_exec.index >= hour_start) & (df_exec.index <= sig_time)]
            
            if developing_1m.empty:
                continue
            
            # Aggregate 1m data into a single "developing" candle
            developing_candle = pd.DataFrame([{
                'Open': developing_1m['Open'].iloc[0],
                'High': developing_1m['High'].max(),
                'Low': developing_1m['Low'].min(),
                'Close': developing_1m['Close'].iloc[-1],
                'Volume': developing_1m['Volume'].sum()
            }], index=[hour_start])
            
            # Get closed hourly candles up to hour_start (exclusive)
            closed_hourly = df_1h_base[df_1h_base.index < hour_start].copy()
            
            if len(closed_hourly) < 200:
                continue  # Not enough data for indicators
            
            # Append developing candle
            combined_data = pd.concat([closed_hourly, developing_candle])
            
            # Create a temporary analyzer to calculate features
            temp_analyzer = StockAnalyzer.__new__(StockAnalyzer)
            temp_analyzer.ticker = ticker
            temp_analyzer.horizon = 'short'
            temp_analyzer.data = combined_data
            
            try:
                df_features = temp_analyzer.prepare_rl_features()
                if df_features.empty:
                    continue
                    
                feature_cols = [c for c in df_features.columns if c not in ['Date', 'Ticker', 'Timestamp', 'Close']]
                last_row = df_features.iloc[-1]
                
                if random_mode:
                    action = np.random.randint(0, 3)
                else:
                    obs = last_row[feature_cols].values.astype(np.float32)
                    account_obs = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                    final_obs = np.concatenate([obs, account_obs])
                    obs_tensor = model.state_to_torch(final_obs)
                    action_tensor = model.agent.select_greedy_action(obs_tensor, eval=True)
                    action = action_tensor.item()
                
                # Apply 15m latency
                signal_valid_from = sig_time + timedelta(minutes=15)
                signal_cache[signal_valid_from] = action
                
            except Exception as e:
                # Skip problematic time points
                continue
        
        print(f"Generated {len(signal_cache)} signals in live mode.")

    # 5. Simulate Loop Over 1m Data
    print("Simulating Execution...")
    
    balance = initial_balance
    shares = 0
    equity_curve = []
    trades = []
    
    current_signal = 0 # HOLD
    last_signal_time = None
    
    sorted_signal_times = sorted(signal_cache.keys())
    next_signal_idx = 0
    
    # We can iterate through 1m bars
    for ts, row in df_exec.iterrows():
        price = row['Close']
        
        # Check if we have a new signal update
        while next_signal_idx < len(sorted_signal_times) and ts >= sorted_signal_times[next_signal_idx]:
             last_signal_time = sorted_signal_times[next_signal_idx]
             current_signal = signal_cache[last_signal_time]
             next_signal_idx += 1
             
        # Execute Strategy based on Current Signal
        if current_signal == 1: # BUY
             if shares == 0:
                 shares = balance / price
                 balance = 0
                 trades.append({'step': ts, 'type': 'buy', 'price': price, 'value': shares * price})
                 
        elif current_signal == 2: # SELL
             if shares > 0:
                 balance = shares * price
                 trades.append({'step': ts, 'type': 'sell', 'price': price, 'value': balance})
                 shares = 0
        
        # Calculate Net Worth
        net_worth = balance + (shares * price)
        equity_curve.append(net_worth)
        
    # 6. Report
    final_net_worth = equity_curve[-1] if equity_curve else initial_balance
    profit = final_net_worth - initial_balance
    roi = (profit / initial_balance) * 100
    
    print("\n" + "="*50)
    print(f" PRODUCTION SIMULATION RESULTS: {ticker}")
    print(f" (Logic: 1H Signal (Closed) -> Executed at Hour:15)")
    print("="*50)
    print(f"Period:      {sim_start} - {sim_end}")
    print(f"Initial:     ₺{initial_balance:,.2f}")
    print(f"Final:       ₺{final_net_worth:,.2f}")
    print(f"Profit:      ₺{profit:,.2f}")
    print(f"ROI:         {roi:.2f}%")
    print(f"Trades:      {len(trades)}")
    print("-" * 50)
    
    # Print Trades
    print(f" {'TIME':<22} | {'ACTION':<6} | {'PRICE':<10}")
    for t in trades:
         print(f" {str(t['step']):<22} | {t['type'].upper():<6} | ₺{t['price']:<9.2f}")
    print("="*50)

    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(df_exec.index, equity_curve, label='Simulated Equity')
    plt.plot(df_exec.index, df_exec['Close'] * (initial_balance / df_exec['Close'].iloc[0]), alpha=0.5, label='Buy & Hold')
    title_suffix = " (RANDOM)" if random_mode else ""
    plt.title(f'Production Simulation: {ticker} (15m Latency){title_suffix}')
    plt.xlabel('Date')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True)
    
    os.makedirs("results", exist_ok=True)
    plot_path = f"results/sim_{ticker}_production.png"
    plt.savefig(plot_path)
    print(f"Plot saved to {plot_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RL Agent Evaluation")
    parser.add_argument("--market", type=str, default="bist100", choices=["bist100", "binance"], help="Market to evaluate")
    parser.add_argument("--ticker", type=str, help="Specific ticker to evaluate (e.g., THYAO.IS or BTCUSDT)")
    parser.add_argument("--days", type=int, default=30, help="Number of days to evaluate (used with --ticker)")
    parser.add_argument("--model", type=str, default=None, help="Path to model file (auto-detected from market if not specified)")
    parser.add_argument("--balance", type=float, default=10000, help="Initial balance for the simulation")
    parser.add_argument("--simulation", action="store_true", help="Run Production Simulation (15m latency, 1m execution)")
    parser.add_argument("--random", action="store_true", help="Run with Random Agent (Benchmark)")
    parser.add_argument("--oracle", action="store_true", help="Show Oracle (Max Profit) Benchmark")
    parser.add_argument("--live", action="store_true", help="Use live/developing candle instead of closed candles")
    
    args = parser.parse_args()
    
    # Auto-detect model path if not specified
    if args.model is None:
        args.model = f"{args.market}_models/{args.market}_ppo_short_agent"
    
    if args.simulation:
        if not args.ticker:
            print("Error: --simulation requires --ticker")
        else:
            backtest_production_simulation(args.ticker, args.model, args.balance, args.random, args.live)
    elif args.ticker:
        evaluate_specific_ticker(args.ticker, args.days, args.model, args.balance, args.random, args.oracle, args.live)
    else:
        # Default dataset evaluation
        data_path = f"{args.market}_data/{args.market}_dataset_short_mid.parquet"
        evaluate_agent(data_path, args.model, args.balance, args.random)
