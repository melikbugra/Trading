import gymnasium as gym
from gymnasium import spaces
import pandas as pd
import numpy as np


class TradingEnv(gym.Env):
    """
    Custom Trading Environment that follows gymnasium interface.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        df,
        initial_balance=10000,
        max_steps=1000,
        commission=0.0,
        market="bist100",
    ):
        super(TradingEnv, self).__init__()

        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.max_steps = max_steps
        self.commission = commission
        self.market = market

        # Action Space: 0: HOLD, 1: BUY, 2: SELL
        self.action_space = spaces.Discrete(3)

        # Extract Prices for Simulation
        # Ensure 'Close' exists. If not, fallback or error.
        if "Close" not in self.df.columns or "Ticker" not in self.df.columns:
            raise ValueError("Dataframe must contain 'Close' and 'Ticker' columns.")

        self.prices = self.df["Close"].values
        self.tickers = self.df["Ticker"].values

        # Observation Space (Exclude Non-Features)
        exclude_cols = ["Date", "Ticker", "Timestamp", "index", "Close", "Datetime"]
        self.feature_cols = [c for c in df.columns if c not in exclude_cols]

        # Pre-compute normalization stats for stable training
        feature_data = self.df[self.feature_cols].values
        self.feature_mean = feature_data.mean(axis=0).astype(np.float32)
        self.feature_std = feature_data.std(axis=0).astype(np.float32)
        self.feature_std[self.feature_std < 1e-8] = 1.0  # Avoid division by zero

        # Determine shape
        self.observation_shape = (
            len(self.feature_cols) + 3,
        )  # Features + Account State

        # Define observation space
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=self.observation_shape, dtype=np.float32
        )

        # State variables
        self.balance = initial_balance
        self.net_worth = initial_balance
        self.shares_held = 0
        self.avg_cost = 0
        self.current_step = 0
        self.max_steps_limit = len(df) - 1

        # Rewards
        self.total_reward = 0
        self.trades = []
        self.peak_net_worth = initial_balance  # For drawdown calculation
        self.steps_since_trade = 0  # Track inactivity

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        self.balance = self.initial_balance
        self.net_worth = self.initial_balance
        self.shares_held = 0
        self.avg_cost = 0
        self.total_reward = 0
        self.trades = []
        self.peak_net_worth = self.initial_balance
        self.steps_since_trade = 0

        # Random Start or Fixed Start via options
        if options and "start_step" in options:
            self.current_step = options["start_step"]
        else:
            # Random Start (Default for training)
            high = len(self.df) - self.max_steps - 1
            if high <= 1:
                self.current_step = 0
            else:
                self.current_step = np.random.randint(0, high)

        self.start_step = self.current_step
        self.end_step = self.current_step + self.max_steps

        return self._next_observation(), {}

    def _next_observation(self):
        # 1. Market Features (normalized to ~N(0,1))
        raw_obs = self.df.iloc[self.current_step][self.feature_cols].values.astype(
            np.float32
        )
        market_obs = (raw_obs - self.feature_mean) / self.feature_std
        # Clip to prevent extreme values
        market_obs = np.clip(market_obs, -3.0, 3.0)

        # 2. Account State
        in_pos = 1.0 if self.shares_held > 0 else 0.0

        unrealized_pnl = 0.0
        if self.shares_held > 0:
            current_price = self.prices[self.current_step]
            if self.avg_cost > 0:
                unrealized_pnl = (current_price - self.avg_cost) / self.avg_cost
                unrealized_pnl = np.clip(unrealized_pnl, -1.0, 1.0)  # Clip PnL too

        time_progress = (self.current_step - self.start_step) / self.max_steps

        account_obs = np.array(
            [in_pos, unrealized_pnl, time_progress], dtype=np.float32
        )

        return np.concatenate([market_obs, account_obs])

    def step(self, action):
        current_price = self.prices[self.current_step]
        current_ticker = self.tickers[self.current_step]

        prev_net_worth = self.net_worth

        # Check next step ticker to detect transition
        next_step = self.current_step + 1
        ticker_changed = False

        if next_step < len(self.df):
            next_ticker = self.tickers[next_step]
            if next_ticker != current_ticker:
                ticker_changed = True

        # Execute Action
        self._take_action(action, current_price)

        # If ticker is changing and we are holding shares, FORCE SELL to avoid price jump artifact
        if ticker_changed and self.shares_held > 0:
            # Sell everything at current price
            # We treat this as a forced exit at end of ticker data
            self._take_action(2, current_price)  # Action 2 = SELL

        self.current_step += 1

        # Update Net Worth
        if self.shares_held > 0:
            # We are holding. Check if we jumped tickers drastically?
            # If ticker_changed logic worked, shares_held should be 0 here.
            # But if we failed to sell, the next price might be huge.
            # Since we move current_step after action, 'self.prices[self.current_step]' is now NEXT price.
            # If we sold, shares_held is 0, so calculating NW based on balance is safe.
            self.net_worth = self.balance + (
                self.shares_held * self.prices[self.current_step]
            )
        else:
            self.net_worth = self.balance

        # Determine Done
        terminated = (
            self.current_step >= self.end_step or self.current_step >= len(self.df) - 1
        )
        truncated = False
        if self.net_worth <= 0:  # Bankruptcy
            terminated = True

        reward = self._calculate_reward(prev_net_worth, action)
        self.total_reward += reward

        obs = self._next_observation()
        info = {
            "net_worth": self.net_worth,
            "total_reward": self.total_reward,
            "shares": self.shares_held,
        }

        return obs, reward, terminated, truncated, info

    def _take_action(self, action, current_price):
        # 0: HOLD, 1: BUY, 2: SELL

        # commission is now self.commission
        commission = self.commission

        # Slippage Simulation - Market Dependent
        # BIST100: yfinance has 15-20 min delay, so random slippage ±0.05%
        # Binance: Real-time data via ccxt, no slippage needed
        if self.market == "binance":
            slippage = 0.0
        else:
            slippage = np.random.uniform(-0.0005, 0.0005)

        if action == 1:  # BUY
            # Buy with all available balance
            if self.balance > 0:
                # Price moves UP against us when buying (Worst case assumption due to delay)
                executed_price = current_price * (1 + slippage)

                # Calculate shares we can buy
                # Commission is 0, so cost is just price
                cost = executed_price * (1 + commission)
                shares_to_buy = int(self.balance / cost)

                if shares_to_buy > 0:
                    total_cost = shares_to_buy * executed_price * (1 + commission)
                    self.balance -= total_cost

                    # Update Avg Cost
                    total_shares = self.shares_held + shares_to_buy

                    old_cost_basis = self.shares_held * self.avg_cost
                    new_cost_basis = shares_to_buy * executed_price
                    self.avg_cost = (old_cost_basis + new_cost_basis) / total_shares

                    self.shares_held += shares_to_buy
                    self.trades.append(
                        {
                            "step": self.current_step,
                            "type": "buy",
                            "price": executed_price,
                        }
                    )
                    self.steps_since_trade = 0  # Reset inactivity counter

        elif action == 2:  # SELL
            # Sell all shares
            if self.shares_held > 0:
                # Price moves DOWN against us when selling
                executed_price = current_price * (1 - slippage)

                revenue = self.shares_held * executed_price * (1 - commission)
                self.balance += revenue
                self.shares_held = 0
                self.avg_cost = 0
                self.trades.append(
                    {"step": self.current_step, "type": "sell", "price": executed_price}
                )
                self.steps_since_trade = 0  # Reset inactivity counter

    def _calculate_reward(self, prev_net_worth, action=0):
        # Simple reward: profit-focused with trade cost awareness

        reward = 0.0

        # 1. Main Signal: Portfolio Return (the primary objective)
        if prev_net_worth > 0 and self.net_worth > 0:
            pct_return = (self.net_worth - prev_net_worth) / prev_net_worth
            reward = pct_return * 100  # 1% gain = +1 reward

        # 2. Trade cost penalty - discourage excessive trading in high-commission markets
        # This helps model learn that each trade has a cost
        if action in [1, 2]:  # BUY or SELL
            trade_penalty = self.commission * 50  # 0.15% commission = -0.075 penalty
            reward -= trade_penalty

        # 3. Completed trade bonus (encourage profitable round trips)
        if action == 2 and self.shares_held == 0:  # Just sold
            if self.net_worth > prev_net_worth:
                reward += 0.5  # Small bonus for profitable exit

        # 4. Update peak for tracking
        if self.net_worth > self.peak_net_worth:
            self.peak_net_worth = self.net_worth

        # Track inactivity
        self.steps_since_trade += 1

        return reward

    def render(self, mode="human", close=False):
        print(f"Step: {self.current_step}")
        print(f"Balance: {self.balance}")
        print(f"Net Worth: {self.net_worth}")
        print(f"Shares: {self.shares_held}")
        print(f"Profit: {self.net_worth - self.initial_balance}")
