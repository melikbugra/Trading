import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from rl_baselines.policy_based.ppo import PPO
from financia.envs.trading_env import TradingEnv
import os
from types import SimpleNamespace
import torch

def evaluate_agent(dataset_path, model_path, initial_balance=10000):
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
    
    # Run Simulation
    obs, _ = env.reset()
    done = False
    
    net_worths = []
    actions = []
    
    print("Running backtest...")
    obs, _ = env.reset()
    
    steps = 0
    while not done:
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
    plt.title(f'Backtest Results: {model_path}')
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

def evaluate_specific_ticker(ticker, days, model_path, initial_balance=10000):
    print(f"\n--- Specific Ticker Evaluation: {ticker} (Last {days} days) ---")
    
    # 1. Fetch Data & Generate Features (reuse logic from DataGenerator)
    # We fetch 2 years to ensure indicators (SMA200 etc) are warm, then slice.
    print(f"Fetching data for {ticker}...")
    try:
        analyzer = StockAnalyzer(ticker, horizon='short-mid', period='2y')
        if analyzer.data is None or len(analyzer.data) < 200:
            print(f"Error: Not enough data for {ticker}")
            return

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
    if not model_path.endswith(".ckpt"):
        model_path += ".ckpt"
        
    print(f"Loading model from {model_path}...")
    try:
        model = PPO(env=env, network_type="mlp", device='cpu')
        model.load(model_path)
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # Run Simulation
    print("Running simulation...")
    obs, _ = env.reset(options={'start_step': 0}) # Force start at 0
    done = False
    
    net_worths = []
    
    while not done:
        obs_tensor = model.state_to_torch(obs)
        action_tensor = model.agent.select_greedy_action(obs_tensor, eval=True)
        action = action_tensor.item()
            
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        
        net_worths.append(info['net_worth'])
        
    # Report Results
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
    
    # Plot
    plt.figure(figsize=(10, 5))
    plt.plot(net_worths, label=f'{ticker} Equity')
    plt.title(f'Evaluation: {ticker} (Last {days} Days)')
    plt.xlabel('Steps (4H Bars)')
    plt.ylabel('Net Worth')
    plt.legend()
    plt.grid(True)
    
    os.makedirs("results", exist_ok=True)
    plot_path = f"results/eval_{ticker}_{days}d.png"
    plt.savefig(plot_path)
    print(f"Plot saved to {plot_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RL Agent Evaluation")
    parser.add_argument("--ticker", type=str, help="Specific ticker to evaluate (e.g., THYAO.IS)")
    parser.add_argument("--days", type=int, default=30, help="Number of days to evaluate (used with --ticker)")
    parser.add_argument("--model", type=str, default="models/ppo_short_mid_agent", help="Path to model file")
    parser.add_argument("--balance", type=float, default=10000, help="Initial balance for the simulation")
    
    args = parser.parse_args()
    
    if args.ticker:
        evaluate_specific_ticker(args.ticker, args.days, args.model, args.balance)
    else:
        evaluate_agent("data/dataset_short_mid.parquet", args.model, args.balance)
