# Teknik Analiz

Simple technical analysis library using Python and yfinance.

## RL Model Architecture

### 1. Observation Space
The model observes a **normalized feature vector** (size ~36) at each timestep:

*   **Market Features (~33 items):**
    *   **Price Dynamics:**
        *   `Log_Return`: Logarithmic percentage change from previous close.
        *   `Shadow_Up/Down`: Size of upper/lower candle shadows (normalized).
        *   `Body`: Size of candle body (Open-Close) (normalized).
    *   **Trend Following:**
        *   `Dist_MA_Short/Long`: % Distance from Short (9) and Long (21/50) Moving Averages.
        *   `Dist_DEMA`, `Dist_KAMA`: Distance from Double EMA and Adaptive MA.
        *   `Dist_SuperTrend`, `SuperTrend_Dir`: Distance from SuperTrend line and Trend Direction (1/-1).
        *   `Ichimoku_TK`: Tenkan-Sen minus Kijun-Sen (Cloud Crossover).
        *   `Ichimoku_Cloud`: Price relative to Kumo Cloud.
        *   `Dist_SAR`: Distance from Parabolic SAR.
        *   `Alligator_Spread`: Jaw minus Lips spread (Trend strength).
        *   `Aroon_Osc`: Aroon Oscillator (100 to -100).
        *   `Dist_Median`: Distance from Median Price.
    *   **Momentum / Oscillators:**
        *   `RSI_Norm`: Relative Strength Index (normalized -1 to 1).
        *   `Stoch_K_Norm`: Stochastic Oscillator %K (normalized).
        *   `Williams_Norm`: Williams %R (normalized).
        *   `Fisher_Norm`: Fisher Transform (Gaussianized price movement).
        *   `MACD_Norm`: MACD Line - Signal Line (normalized distance).
        *   `CCI_Norm`: Commodity Channel Index (normalized).
    *   **Volume & Money Flow:**
        *   `Rel_Volume`: Current volume vs 20-period Average.
        *   `CMF`: Chaikin Money Flow (-1 to 1).
        *   `MFI_Norm`: Money Flow Index (normalized).
        *   `OBV_Z`: On-Balance Volume (Z-Score of 20 periods).
        *   `Dist_VWAP`: % Distance from Intraday VWAP.
        *   `Demand_Index_Norm`: Buying vs Selling Pressure.
    *   **Divergence Proxies (Rolling Correlation):**
        *   `RSI_Correl`, `MACD_Correl`, `CCI_Correl`, `OBV_Correl`
        *   `Stoch_Correl`, `Williams_Correl`, `Fisher_Correl`
        *   `CMF_Correl`, `MFI_Correl`, `Demand_Correl`
        *   *(Negative values in these 10 features indicate potential divergence)*
    *   **Volatility:**
        *   `ATR_Pct`: Average True Range as % of Price.
        *   `BB_Width`: Bollinger Band Width (Vol expansion/contraction).
        *   `ADX_Norm`: Trend Strength (0-1).
        *   `DMI_Dir`: Directional Movement (Positive DI - Negative DI).
        *   `WaveTrend_Diff`: WaveTrend Oscillator Difference.
*   **Account State (3):**
    *   `In_Position` (0 or 1)
    *   `Unrealized_PnL` (Percentage)
    *   `Time_Progress` (0.0 to 1.0)

### 2. Action Space
`Discrete(3)`:
*   `0`: **HOLD** (Do nothing)
*   `1`: **BUY** (Invest 100% of available balance)
*   `2`: **SELL** (Liquidate 100% of holdings)

### 3. Reward Function
The agent receives a **Continuous Reward** at every timestep (Hourly), not just when selling. This helps the PPO algorithm connect actions to immediate consequences.

**Formula:**
```python
Reward = ( (NetWorth_t+1 - NetWorth_t) / Initial_Balance ) * 100  -  Time_Penalty
```

*   **P&L Component:**
    *   Changes in portfolio value (Realized or Unrealized) are rewarded immediately.
    *   **Scaling:** A **1% increase** in total portfolio value = **+1.0 Reward**.
    *   This normalization prevents huge rewards as the portfolio grows, keeping gradients stable.
*   **Time Penalty (-0.001):**
    *   Applied every hour if the agent is holding a stock.
    *   **Logic:** Acts as an "Opportunity Cost" or "Risk-Free Rate".
    *   **Effect:** The agent learns that "Time is Money". If a stock is flat, it slowly loses points. It is forced to find trends that yield at least **>0.001% per hour** to justify holding.

### 4. Training
*   **Algorithm:** PPO (Proximal Policy Optimization) from `sb3` via `rl-baselines`.
*   **Network:** MLP (Multi-Layer Perceptron), size `[64, 64]`.
*   **Data:** 2 Years of BIST100 Hourly Data.
*   **Environment:** Zero Commission, Zero Slippage (Optimized for Trend Following).
