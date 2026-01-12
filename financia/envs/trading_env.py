import gymnasium as gym
from gymnasium import spaces
import pandas as pd
import numpy as np

class TradingEnv(gym.Env):
    """
    Custom Trading Environment that follows gymnasium interface.
    """
    metadata = {'render_modes': ['human']}

    def __init__(self, df, initial_balance=10000, max_steps=1000):
        super(TradingEnv, self).__init__()
        
        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.max_steps = max_steps
        
        # Action Space: 0: HOLD, 1: BUY, 2: SELL
        self.action_space = spaces.Discrete(3)
        
        # Extract Prices for Simulation
        # Ensure 'Close' exists. If not, fallback or error.
        if 'Close' not in self.df.columns or 'Ticker' not in self.df.columns:
             raise ValueError("Dataframe must contain 'Close' and 'Ticker' columns.")
             
        self.prices = self.df['Close'].values
        self.tickers = self.df['Ticker'].values
        
        # Observation Space (Exclude Non-Features)
        exclude_cols = ['Date', 'Ticker', 'Timestamp', 'index', 'Close', 'Datetime']
        self.feature_cols = [c for c in df.columns if c not in exclude_cols]
        
        # Determine shape
        self.observation_shape = (len(self.feature_cols) + 3,) # Features + Account State
        
        # Define observation space
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=self.observation_shape, dtype=np.float32)
        
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

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        self.balance = self.initial_balance
        self.net_worth = self.initial_balance
        self.shares_held = 0
        self.avg_cost = 0
        self.total_reward = 0
        self.trades = []
        
        # Random Start or Fixed Start via options
        if options and 'start_step' in options:
            self.current_step = options['start_step']
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
        # 1. Market Features
        # Efficiently slice numpy array
        market_obs = self.df.iloc[self.current_step][self.feature_cols].values.astype(np.float32)
        
        # 2. Account State
        in_pos = 1.0 if self.shares_held > 0 else 0.0
        
        unrealized_pnl = 0.0
        if self.shares_held > 0:
            current_price = self.prices[self.current_step]
            if self.avg_cost > 0:
                unrealized_pnl = (current_price - self.avg_cost) / self.avg_cost
        
        time_progress = (self.current_step - self.start_step) / self.max_steps
        
        account_obs = np.array([in_pos, unrealized_pnl, time_progress], dtype=np.float32)
        
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
            self._take_action(2, current_price) # Action 2 = SELL
        
        self.current_step += 1
        
        # Update Net Worth
        if self.shares_held > 0:
            # We are holding. Check if we jumped tickers drastically?
            # If ticker_changed logic worked, shares_held should be 0 here.
            # But if we failed to sell, the next price might be huge.
            # Since we move current_step after action, 'self.prices[self.current_step]' is now NEXT price.
            # If we sold, shares_held is 0, so calculating NW based on balance is safe.
            self.net_worth = self.balance + (self.shares_held * self.prices[self.current_step])
        else:
            self.net_worth = self.balance
            
        # Determine Done
        terminated = self.current_step >= self.end_step or self.current_step >= len(self.df) - 1
        truncated = False
        if self.net_worth <= 0: # Bankruptcy
            terminated = True
        
        reward = self._calculate_reward(prev_net_worth)
        self.total_reward += reward
        
        obs = self._next_observation()
        info = {
            'net_worth': self.net_worth,
            'total_reward': self.total_reward,
            'shares': self.shares_held
        }
        
        return obs, reward, terminated, truncated, info

    def _take_action(self, action, current_price):
        # 0: HOLD, 1: BUY, 2: SELL
        
        commission = 0.001 # 0.1%
        
        if action == 1: # BUY
            # Buy with all available balance
            if self.balance > 0:
                # Calculate shares we can buy
                cost = current_price * (1 + commission)
                shares_to_buy = int(self.balance / cost)
                
                if shares_to_buy > 0:
                    total_cost = shares_to_buy * current_price * (1 + commission)
                    self.balance -= total_cost
                    
                    # Update Avg Cost
                    total_shares = self.shares_held + shares_to_buy
                    # New avg cost = old_total_val + new_total_val / total_shares (simplified: weighted avg of price paid)
                    # Actually keeping track of avg entry price
                    old_cost_basis = self.shares_held * self.avg_cost
                    new_cost_basis = shares_to_buy * current_price # Before commission? Entry price logic
                    self.avg_cost = (old_cost_basis + new_cost_basis) / total_shares
                    
                    self.shares_held += shares_to_buy
                    self.trades.append({'step': self.current_step, 'type': 'buy', 'price': current_price})
                    
        elif action == 2: # SELL
            # Sell all shares
            if self.shares_held > 0:
                revenue = self.shares_held * current_price * (1 - commission)
                self.balance += revenue
                self.shares_held = 0
                self.avg_cost = 0
                self.trades.append({'step': self.current_step, 'type': 'sell', 'price': current_price})
                
    def _calculate_reward(self, prev_net_worth):
        # Reward = Change in Net Worth - Time Penalty
        
        # 1. Shaping (Net Worth Change)
        # Includes Realized and Unrealized PnL and Costs automatically
        reward = (self.net_worth - prev_net_worth) / self.initial_balance # Normalized by initial balance
        
        # Scale it up to make it meaningful for gradient
        reward *= 100 
        
        # 2. Time Penalty
        # If in position, penalize slightly to encourage efficiency?
        # Net worth change already penalizes stagnation if inflation/opportunity cost existed, but here we explicitly add it.
        if self.shares_held > 0:
             reward -= 0.001 # Small rent
             
        return reward

    def render(self, mode='human', close=False):
        print(f'Step: {self.current_step}')
        print(f'Balance: {self.balance}')
        print(f'Net Worth: {self.net_worth}')
        print(f'Shares: {self.shares_held}')
        print(f'Profit: {self.net_worth - self.initial_balance}')
