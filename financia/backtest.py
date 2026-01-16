"""
Comprehensive Backtest Script

Evaluates model performance with realistic metrics:
- Win Rate, Sharpe Ratio, Max Drawdown, Profit Factor
- Trade-by-trade analysis
- Comparison with Buy & Hold
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from financia.get_model_decision import InferenceEngine
from financia.analyzer import StockAnalyzer
import os
import argparse

# Top liquid BIST100 stocks for testing
TEST_TICKERS_BIST = [
    "THYAO.IS", "GARAN.IS", "AKBNK.IS", "EREGL.IS", "SISE.IS",
    "KCHOL.IS", "TUPRS.IS", "SAHOL.IS", "YKBNK.IS", "FROTO.IS",
    "ASELS.IS", "BIMAS.IS", "TCELL.IS", "PGSUS.IS", "TAVHL.IS"
]

TEST_TICKERS_BINANCE = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"
]


class BacktestEngine:
    def __init__(self, model_path, market='bist100', initial_balance=10000):
        self.engine = InferenceEngine(model_path)
        self.market = market
        self.initial_balance = initial_balance
        self.slippage = 0.002  # 0.2% slippage (matches training)
        self.commission = 0.0 if market == 'bist100' else 0.0015

    def run_single_ticker_backtest(self, ticker, days=180, verbose=False):
        """
        Run backtest on a single ticker for specified number of days.
        Returns trade log and metrics.
        """
        if verbose:
            print(f"\n{'='*50}")
            print(f"Backtesting: {ticker} (Last {days} days)")
            print('='*50)

        # Fetch data
        try:
            analyzer = StockAnalyzer(ticker, horizon='short', period=f'{days + 60}d', market=self.market)
            if analyzer.data is None or len(analyzer.data) < 200:
                return None, None
        except Exception as e:
            if verbose:
                print(f"Error fetching data: {e}")
            return None, None

        # Prepare features
        df = analyzer.prepare_rl_features()
        if df.empty:
            return None, None

        # Filter to test period (last N days)
        cutoff = df.index.max() - timedelta(days=days)
        df_test = df[df.index >= cutoff].copy()

        if len(df_test) < 50:
            if verbose:
                print(f"Not enough test data: {len(df_test)} bars")
            return None, None

        # Simulation state
        balance = self.initial_balance
        shares = 0
        entry_price = 0

        trades = []
        equity_curve = []

        # Feature columns
        exclude_cols = ['Date', 'Ticker', 'Timestamp', 'index', 'Close', 'Datetime']
        feature_cols = [c for c in df_test.columns if c not in exclude_cols]

        # Make sure model is loaded
        if self.engine.model is None:
            self.engine.load_model()

        # Iterate through test period
        prev_action = 0

        for i, (timestamp, row) in enumerate(df_test.iterrows()):
            current_price = row['Close']

            # Get model prediction
            obs = row[feature_cols].values.astype(np.float32)

            # Account state
            in_pos = 1.0 if shares > 0 else 0.0
            unrealized_pnl = 0.0
            if shares > 0 and entry_price > 0:
                unrealized_pnl = (current_price - entry_price) / entry_price

            account_obs = np.array([in_pos, unrealized_pnl, 0.5], dtype=np.float32)
            final_obs = np.concatenate([obs, account_obs])

            # Predict
            state_tensor = self.engine.model.state_to_torch(final_obs)
            action_tensor = self.engine.model.agent.select_greedy_action(state_tensor, eval=True)
            action = action_tensor.item()

            # Execute action
            if action == 1 and shares == 0:  # BUY
                exec_price = current_price * (1 + self.slippage)
                cost = exec_price * (1 + self.commission)
                shares = balance / cost
                balance = 0
                entry_price = exec_price
                trades.append({
                    'timestamp': timestamp,
                    'type': 'BUY',
                    'price': exec_price,
                    'shares': shares
                })

            elif action == 2 and shares > 0:  # SELL
                exec_price = current_price * (1 - self.slippage)
                revenue = shares * exec_price * (1 - self.commission)

                # Record trade result
                pnl_pct = (exec_price - entry_price) / entry_price * 100
                trades.append({
                    'timestamp': timestamp,
                    'type': 'SELL',
                    'price': exec_price,
                    'shares': shares,
                    'pnl_pct': pnl_pct,
                    'entry_price': entry_price
                })

                balance = revenue
                shares = 0
                entry_price = 0

            # Track equity
            net_worth = balance + (shares * current_price)
            equity_curve.append({
                'timestamp': timestamp,
                'net_worth': net_worth,
                'price': current_price
            })

            prev_action = action

        # Force close if still in position
        if shares > 0:
            final_price = df_test['Close'].iloc[-1] * (1 - self.slippage)
            pnl_pct = (final_price - entry_price) / entry_price * 100
            trades.append({
                'timestamp': df_test.index[-1],
                'type': 'SELL (FORCED)',
                'price': final_price,
                'shares': shares,
                'pnl_pct': pnl_pct,
                'entry_price': entry_price
            })
            balance = shares * final_price * (1 - self.commission)
            shares = 0

        return trades, equity_curve

    def calculate_metrics(self, trades, equity_curve):
        """Calculate comprehensive performance metrics."""
        if not trades or not equity_curve:
            return None

        # Separate completed trades (SELL only)
        completed_trades = [t for t in trades if 'pnl_pct' in t]

        if not completed_trades:
            return None

        # Basic metrics
        total_trades = len(completed_trades)
        winning_trades = [t for t in completed_trades if t['pnl_pct'] > 0]
        losing_trades = [t for t in completed_trades if t['pnl_pct'] <= 0]

        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

        # PnL metrics
        pnls = [t['pnl_pct'] for t in completed_trades]
        avg_win = np.mean([t['pnl_pct'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl_pct'] for t in losing_trades]) if losing_trades else 0

        # Profit factor
        gross_profit = sum([t['pnl_pct'] for t in winning_trades]) if winning_trades else 0
        gross_loss = abs(sum([t['pnl_pct'] for t in losing_trades])) if losing_trades else 0.001
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Equity curve analysis
        equity_df = pd.DataFrame(equity_curve)
        equity_df.set_index('timestamp', inplace=True)

        # Returns
        equity_df['returns'] = equity_df['net_worth'].pct_change()

        # Sharpe Ratio (annualized, assuming hourly data)
        # ~252 trading days * ~7 hours = ~1764 trading hours per year
        if equity_df['returns'].std() > 0:
            sharpe = equity_df['returns'].mean() / equity_df['returns'].std() * np.sqrt(1764)
        else:
            sharpe = 0

        # Max Drawdown
        equity_df['peak'] = equity_df['net_worth'].cummax()
        equity_df['drawdown'] = (equity_df['peak'] - equity_df['net_worth']) / equity_df['peak']
        max_drawdown = equity_df['drawdown'].max() * 100

        # Total Return
        initial = equity_df['net_worth'].iloc[0]
        final = equity_df['net_worth'].iloc[-1]
        total_return = (final - initial) / initial * 100

        # Buy & Hold comparison
        price_initial = equity_df['price'].iloc[0]
        price_final = equity_df['price'].iloc[-1]
        buy_hold_return = (price_final - price_initial) / price_initial * 100

        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'total_return': total_return,
            'buy_hold_return': buy_hold_return,
            'alpha': total_return - buy_hold_return  # Excess return vs B&H
        }

    def run_full_backtest(self, tickers=None, days=180):
        """Run backtest across multiple tickers."""
        if tickers is None:
            tickers = TEST_TICKERS_BIST if self.market == 'bist100' else TEST_TICKERS_BINANCE

        all_results = []
        all_trades = []

        print(f"\n{'='*60}")
        print(f"COMPREHENSIVE BACKTEST - {self.market.upper()}")
        print(f"Period: Last {days} days | Tickers: {len(tickers)}")
        print(f"Slippage: {self.slippage*100:.2f}% | Commission: {self.commission*100:.2f}%")
        print('='*60)

        for ticker in tickers:
            trades, equity = self.run_single_ticker_backtest(ticker, days, verbose=False)

            if trades and equity:
                metrics = self.calculate_metrics(trades, equity)
                if metrics:
                    metrics['ticker'] = ticker
                    all_results.append(metrics)
                    all_trades.extend(trades)

                    status = "OK" if metrics['total_return'] > 0 else "LOSS"
                    print(f"  {ticker:<12} | Trades: {metrics['total_trades']:>3} | "
                          f"Win: {metrics['win_rate']:>5.1f}% | "
                          f"Return: {metrics['total_return']:>7.2f}% | "
                          f"B&H: {metrics['buy_hold_return']:>7.2f}% | [{status}]")
            else:
                print(f"  {ticker:<12} | SKIPPED (insufficient data)")

        if not all_results:
            print("\nNo valid backtest results!")
            return None

        # Aggregate metrics
        df_results = pd.DataFrame(all_results)

        print(f"\n{'='*60}")
        print("AGGREGATE RESULTS")
        print('='*60)

        # Summary statistics
        total_trades = df_results['total_trades'].sum()
        total_wins = df_results['winning_trades'].sum()
        total_losses = df_results['losing_trades'].sum()
        overall_win_rate = total_wins / total_trades * 100 if total_trades > 0 else 0

        avg_return = df_results['total_return'].mean()
        avg_buy_hold = df_results['buy_hold_return'].mean()
        avg_sharpe = df_results['sharpe_ratio'].mean()
        avg_max_dd = df_results['max_drawdown'].mean()
        avg_profit_factor = df_results['profit_factor'].mean()

        # Print summary
        print(f"\n  Total Trades:      {total_trades}")
        print(f"  Winning Trades:    {total_wins}")
        print(f"  Losing Trades:     {total_losses}")
        print(f"\n  Overall Win Rate:  {overall_win_rate:.1f}%")
        print(f"  Avg Profit Factor: {avg_profit_factor:.2f}")
        print(f"  Avg Sharpe Ratio:  {avg_sharpe:.2f}")
        print(f"  Avg Max Drawdown:  {avg_max_dd:.1f}%")
        print(f"\n  Avg Model Return:  {avg_return:.2f}%")
        print(f"  Avg Buy&Hold:      {avg_buy_hold:.2f}%")
        print(f"  Avg Alpha:         {avg_return - avg_buy_hold:.2f}%")

        # Verdict
        print(f"\n{'='*60}")
        print("VERDICT")
        print('='*60)

        score = 0
        verdicts = []

        # Win rate check
        if overall_win_rate >= 55:
            verdicts.append(f"  [PASS] Win Rate: {overall_win_rate:.1f}% >= 55%")
            score += 1
        elif overall_win_rate >= 50:
            verdicts.append(f"  [WARN] Win Rate: {overall_win_rate:.1f}% (borderline)")
            score += 0.5
        else:
            verdicts.append(f"  [FAIL] Win Rate: {overall_win_rate:.1f}% < 50%")

        # Sharpe check
        if avg_sharpe >= 1.5:
            verdicts.append(f"  [PASS] Sharpe Ratio: {avg_sharpe:.2f} >= 1.5")
            score += 1
        elif avg_sharpe >= 1.0:
            verdicts.append(f"  [WARN] Sharpe Ratio: {avg_sharpe:.2f} (acceptable)")
            score += 0.5
        else:
            verdicts.append(f"  [FAIL] Sharpe Ratio: {avg_sharpe:.2f} < 1.0")

        # Drawdown check
        if avg_max_dd <= 15:
            verdicts.append(f"  [PASS] Max Drawdown: {avg_max_dd:.1f}% <= 15%")
            score += 1
        elif avg_max_dd <= 25:
            verdicts.append(f"  [WARN] Max Drawdown: {avg_max_dd:.1f}% (high)")
            score += 0.5
        else:
            verdicts.append(f"  [FAIL] Max Drawdown: {avg_max_dd:.1f}% > 25%")

        # Alpha check
        alpha = avg_return - avg_buy_hold
        if alpha > 5:
            verdicts.append(f"  [PASS] Alpha: {alpha:.2f}% > Buy&Hold")
            score += 1
        elif alpha > 0:
            verdicts.append(f"  [WARN] Alpha: {alpha:.2f}% (slight edge)")
            score += 0.5
        else:
            verdicts.append(f"  [FAIL] Alpha: {alpha:.2f}% (underperforms B&H)")

        # Profit factor check
        if avg_profit_factor >= 1.5:
            verdicts.append(f"  [PASS] Profit Factor: {avg_profit_factor:.2f} >= 1.5")
            score += 1
        elif avg_profit_factor >= 1.2:
            verdicts.append(f"  [WARN] Profit Factor: {avg_profit_factor:.2f} (acceptable)")
            score += 0.5
        else:
            verdicts.append(f"  [FAIL] Profit Factor: {avg_profit_factor:.2f} < 1.2")

        for v in verdicts:
            print(v)

        print(f"\n  TRUST SCORE: {score}/5")

        if score >= 4:
            print("\n  RECOMMENDATION: Model is TRUSTWORTHY for live trading")
            print("                  Start with small positions, monitor closely")
        elif score >= 2.5:
            print("\n  RECOMMENDATION: Model needs IMPROVEMENT")
            print("                  Paper trade first, identify weak points")
        else:
            print("\n  RECOMMENDATION: Model is NOT READY for live trading")
            print("                  Significant improvements needed")

        print('='*60)

        # Save results
        os.makedirs("results", exist_ok=True)
        df_results.to_csv(f"results/backtest_{self.market}_{days}d.csv", index=False)
        print(f"\nDetailed results saved to: results/backtest_{self.market}_{days}d.csv")

        return df_results


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Backtest")
    parser.add_argument("--market", type=str, default="bist100", choices=["bist100", "binance"])
    parser.add_argument("--days", type=int, default=180, help="Backtest period in days")
    parser.add_argument("--model", type=str, default=None, help="Model path (auto-detected if not specified)")

    args = parser.parse_args()

    # Auto-detect model path
    if args.model is None:
        args.model = f"{args.market}_models/{args.market}_ppo_short_agent"

    # Run backtest
    engine = BacktestEngine(args.model, args.market)
    results = engine.run_full_backtest(days=args.days)


if __name__ == "__main__":
    main()
