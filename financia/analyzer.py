import yfinance as yf
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# Try importing ccxt for crypto
try:
    import ccxt
except ImportError:
    ccxt = None



# Import indicator config for market/timeframe-aware parameters
try:
    from financia.indicator_config import get_config
except ImportError:
    get_config = None

class StockAnalyzer:
    def __init__(self, ticker, horizon='medium', period=None, interval=None, start=None, end=None, market=None):
        """
        Initializes the StockAnalyzer with a specific stock ticker and trading horizon.
        
        Args:
            ticker (str): The stock ticker symbol (e.g., 'THYAO.IS' or 'BTCUSDT').
            horizon (str): Trading horizon ('short', 'medium', 'long').
            period (str, optional): Override default period.
            interval (str, optional): Override default interval.
            start (str/datetime, optional): Start date for fetching data.
            end (str/datetime, optional): End date for fetching data.
            market (str, optional): 'bist100' or 'binance'. If None, inferred from ticker.
        """
        self.ticker = ticker
        self.horizon = horizon.lower()
        
        # Infer market if not provided
        if market:
            self.market = market.lower()
        else:
            if ticker.endswith('USDT') or ticker.endswith('BUSD'):
                self.market = 'binance'
            else:
                self.market = 'bist100'  # Default to BIST100/Yahoo
        
        # Fetch Data based on Market
        if self.market == 'binance':
            self._fetch_binance_data(period, interval, start, end)
        else:
            self._fetch_yahoo_data(period, interval, start, end)

        if self.data.empty:
            print(f"Warning: No data found for ticker {ticker} ({self.market})")
            self.data = pd.DataFrame() # Empty DF

    def _fetch_yahoo_data(self, period, interval, start, end):
        """Fetch data from Yahoo Finance (Stocks)"""
        # Default defaults
        if period is None or interval is None:
            if self.horizon == 'short':
                _period = "730d" 
                _interval = "60m"
            elif self.horizon == 'short-mid':
                _period = "2y" 
                _interval = "1h"
            elif self.horizon == 'long':
                _period = "5y"
                _interval = "1wk"
            else: # medium
                _period = "1y"
                _interval = "1d"
        
        use_period = period if period else _period
        use_interval = interval if interval else _interval
            
        self.stock = yf.Ticker(self.ticker)
        
        if start:
            self.data = self.stock.history(start=start, end=end, interval=use_interval)
        else:
            self.data = self.stock.history(period=use_period, interval=use_interval)
        
        if isinstance(self.data.columns, pd.MultiIndex):
            self.data.columns = self.data.columns.get_level_values(0)

        # Resample for Short-Mid (4H) support
        if self.horizon == 'short-mid' and not self.data.empty:
            self.data = self.data.dropna()
            agg_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
            agg_dict = {k:v for k,v in agg_dict.items() if k in self.data.columns}
            self.data = self.data.resample('4h', origin='start').agg(agg_dict).dropna()

    def _fetch_binance_data(self, period, interval, start, end):
        """Fetch data from Binance via CCXT (Crypto)"""
        if ccxt is None:
            print("Error: ccxt library not found. Cannot fetch Binance data.")
            self.data = pd.DataFrame()
            return

        # Determine interval based on horizon (aligned with indicator_config/data_generator)
        # Or use provided override
        if interval:
            use_interval = interval
        else:
            if self.horizon == 'short':
                use_interval = '1m'
            elif self.horizon == 'mid' or self.horizon == 'short-mid':
                use_interval = '15m'
            elif self.horizon == 'long':
                use_interval = '4h'
            else:
                use_interval = '1h' # Fallback
                
        # Determine duration (days)
        # If period string provided (e.g. "730d"), parse it. 
        # For simplicity, if not provided, use reasonable defaults.
        days = 30 # Default
        if period:
             # Try simple parsing
             if period.endswith('d'):
                 try:
                     days = int(period[:-1])
                 except: pass
        else:
            if self.horizon == 'short': days = 5 # small fetch for live analysis
            elif self.horizon == 'mid': days = 60
            elif self.horizon == 'long': days = 365
            else: days = 30
            
        exchange = ccxt.binance({'enableRateLimit': True})
        since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        # Simple fetch loop (don't need massive history for live analysis usually, but enough for indicators ~200-500)
        # If we need massive history for backtesting, use data generator.
        # Here we just need enough for indicators (e.g. 500 candles).
        limit = 1000
        
        try:
             ohlcv = exchange.fetch_ohlcv(self.ticker, use_interval, limit=limit) # Fetch latest
             if not ohlcv:
                 self.data = pd.DataFrame()
                 return
                 
             df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
             df['Datetime'] = pd.to_datetime(df['Timestamp'], unit='ms')
             df.set_index('Datetime', inplace=True)
             df.drop('Timestamp', axis=1, inplace=True)
             self.data = df
             
        except Exception as e:
            print(f"Error fetching Binance data for {self.ticker}: {e}")
            self.data = pd.DataFrame()

    def _calculate_divergence_series(self, indicator, window=60):
        """
        Calculates divergence signal for the entire series.
        Returns a Series of 1 (Bullish), -1 (Bearish), 0 (None).
        """
        price = self.data['Close']
        div_series = pd.Series(0, index=self.data.index, dtype=float)
        
        # Identify Peaks and Troughs (Simple Shift)
        # 1 means Peak, -1 means Trough, 0 means None
        
        # We need peaks of Price AND Indicator
        # This is a bit heavy loop for Python.
        # Let's try to be efficient.
        # Just iterate from window to end.
        
        # Pre-compute peaks? No, peaks are contextual to the window? 
        # Actually peaks are local maxima, independent of window edge (mostly).
        
        # Let's use the exact logic from _check_divergence but slid over time.
        # To avoid lag, we only care if a divergence JUST completed?
        # Or if we represent a "State" of divergence?
        # RL usually benefits from "State".
        
        # Optimization: run _check_divergence logic on every row? 
        # With 3000 rows, it might take 1-2 seconds. Acceptable for prep.
        
        # BUT _check_divergence needs 'self' to access data['Close']. 
        # It slices via iloc. 
        # Let's replicate logic in a loop.
        
        close_vals = price.values
        ind_vals = indicator.values
        div_out = np.zeros(len(price))
        
        for i in range(window, len(price)):
            # Window slice
            p_slice = close_vals[i-window:i+1]
            i_slice = ind_vals[i-window:i+1]
            
            # Find Peaks (Indices in slice)
            # Naive peak finding: val > prev and val > next
            # We need at least 2 peaks.
            
            # This is complex to code in one shot without error.
            # Alternative: Detection of "Divergence Condition" usually happens when a new peak/trough is confirmed.
            # Let's use a simplified heuristic for RL efficiency.
            # "Is Current Price Making Lower Low while Indicator Making Higher Low?" (Rolling Correlation?)
            # Rolling Correlation of Price vs Indicator.
            # If Corr is negative -> Divergence? 
            # Normal: Price Up, Ind Up (Corr > 0).
            # Divergence: Price Up, Ind Down (Corr < 0).
            # THIS IS MUCH FASTER AND ROBUST!
            # Bullish Div: Price Down, Ind Up.
            # Bearish Div: Price Up, Ind Down.
            # In both cases, Correlation becomes negative.
            
            pass 
        
        # REPLACING WITH ROLLING CORRELATION APPROACH
        # It acts as a proxy for divergence.
        # If Correlation(Price, Indicator) < -0.5 (or similar threshold), it indicates potential divergence.
        # Let's return the Correlation itself! The RL can learn "Negative Correlation = Divergence".
        # This is strictly better than binary 1/0/1 because it's continuous.
        
        return price.rolling(window=window).corr(indicator).fillna(0)

    def _check_divergence(self, indicator, lookback=60):

        """
        Checks for divergence between Price and Indicator.
        Returns: 
         1: Bullish Divergence (Price Lower Low, Indicator Higher Low)
        -1: Bearish Divergence (Price Higher High, Indicator Lower High)
         0: No Divergence
        """
        # Get Price and Indicator series
        price = self.data['Close'].iloc[-lookback:]
        ind = indicator.iloc[-lookback:]
        
        # Find peaks (highs)
        price_peaks = (price.shift(1) < price) & (price.shift(-1) < price)
        ind_peaks = (ind.shift(1) < ind) & (ind.shift(-1) < ind)
        
        # Find troughs (lows)
        price_troughs = (price.shift(1) > price) & (price.shift(-1) > price)
        ind_troughs = (ind.shift(1) > ind) & (ind.shift(-1) > ind)
        
        # Get indices
        p_peaks_idx = price[price_peaks].index
        i_peaks_idx = ind[ind_peaks].index
        
        p_troughs_idx = price[price_troughs].index
        i_troughs_idx = ind[ind_troughs].index
        
        divergence = 0
        
        # Check Bearish Divergence (Highs)
        # Price HH, Ind LH
        if len(p_peaks_idx) >= 2 and len(i_peaks_idx) >= 2:
            if price[p_peaks_idx[-1]] > price[p_peaks_idx[-2]] and ind[i_peaks_idx[-1]] < ind[i_peaks_idx[-2]]:
                divergence = -1

        # Check Bullish Divergence (Lows)
        # Price LL, Ind HL
        # Only override if we found bullish (or check priority? typically one prevails)
        if len(p_troughs_idx) >= 2 and len(i_troughs_idx) >= 2:
            if price[p_troughs_idx[-1]] < price[p_troughs_idx[-2]] and ind[i_troughs_idx[-1]] > ind[i_troughs_idx[-2]]:
                divergence = 1
                
        return divergence

    def _calculate_rsi(self, window=14):
        """
        Calculates the Relative Strength Index (RSI).
        """
        delta = self.data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, fast=12, slow=26, signal=9):
        """
        Calculates the Moving Average Convergence Divergence (MACD).
        """
        exp1 = self.data['Close'].ewm(span=fast, adjust=False).mean()
        exp2 = self.data['Close'].ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    def get_rsi_decision(self):
        """
        Returns BUY/SELL/HOLD decision based on RSI.
        RSI < 30 -> BUY
        RSI > 70 -> SELL
        Else -> HOLD
        """
        rsi = self._calculate_rsi()
        current_rsi = rsi.iloc[-1]
        
        # Divergence Check
        div = self._check_divergence(rsi)

        if current_rsi < 30:
            return "BUY", current_rsi, div
        elif current_rsi > 70:
            return "SELL", current_rsi, div
        else:
            return "HOLD", current_rsi, div

    def get_macd_decision(self):
        """
        Returns decision based on MACD.
        """
        macd, signal_line = self._calculate_macd()
        
        # Check the last two points to confirm crossover
        current_macd = macd.iloc[-1]
        current_signal = signal_line.iloc[-1]
        prev_macd = macd.iloc[-2]
        prev_signal = signal_line.iloc[-2]

        decision = "NEUTRAL"
        
        # Bullish Crossover
        if prev_macd < prev_signal and current_macd > current_signal:
            decision = "BUY"
        # Bearish Crossover
        elif prev_macd > prev_signal and current_macd < current_signal:
            decision = "SELL"
        # Trend continuation
        elif current_macd > current_signal:
             decision = "HOLD"
        elif current_macd < current_signal:
             decision = "SELL"
             
             
        # Divergence Check (on MACD Histogram or MACD Line? Using MACD Line)
        div = self._check_divergence(macd)

        return decision, (current_macd, current_signal), div

    def _calculate_bollinger_bands(self, window=20, num_std=2):
        """
        Calculates Bollinger Bands.
        Returns: upper_band, middle_band, lower_band
        """
        middle_band = self.data['Close'].rolling(window=window).mean()
        std_dev = self.data['Close'].rolling(window=window).std()
        
        upper_band = middle_band + (std_dev * num_std)
        lower_band = middle_band - (std_dev * num_std)
        return upper_band, middle_band, lower_band

    def get_bollinger_decision(self):
        """
        Returns decision based on Bollinger Bands.
        """
        upper, middle, lower = self._calculate_bollinger_bands()
        
        current_price = self.data['Close'].iloc[-1]
        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        
        if current_price < current_lower:
            return "BUY", (current_price, current_lower, current_upper), 0
        elif current_price > current_upper:
            return "SELL", (current_price, current_lower, current_upper), 0
        else:
            return "HOLD", (current_price, current_lower, current_upper), 0

    def _calculate_dmi(self, window=14):
        """
        Calculates DMI and ADX (Wells Wilder's Smoothing).
        Returns: adx, plus_di, minus_di
        """
        # Calculate True Range (TR)
        high = self.data['High']
        low = self.data['Low']
        close = self.data['Close']
        
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate Directional Movement (DM)
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Convert to Series for rolling operations
        plus_dm = pd.Series(plus_dm, index=self.data.index)
        minus_dm = pd.Series(minus_dm, index=self.data.index)
        
        # Wilder's Smoothing Function
        def wilder_smooth(series, window):
            return series.ewm(alpha=1/window, adjust=False).mean()

        tr_smooth = wilder_smooth(tr, window)
        plus_dm_smooth = wilder_smooth(plus_dm, window)
        minus_dm_smooth = wilder_smooth(minus_dm, window)
        
        # Calculate DI
        plus_di = 100 * (plus_dm_smooth / tr_smooth)
        minus_di = 100 * (minus_dm_smooth / tr_smooth)
        
        # Calculate ADX
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
        adx = wilder_smooth(dx, window)
        
        return adx, plus_di, minus_di

    def get_dmi_decision(self):
        """
        Returns decision based on ADX and DI values.
        """
        adx, plus_di, minus_di = self._calculate_dmi()
        
        curr_adx = adx.iloc[-1]
        curr_plus = plus_di.iloc[-1]
        curr_minus = minus_di.iloc[-1]
        
        decision = "NEUTRAL"
        
        if curr_adx > 25:
            if curr_plus > curr_minus:
                decision = "STRONG BUY"
            else:
                decision = "STRONG SELL"
        elif curr_adx < 20:
            decision = "NEUTRAL"
        else:
            # ADX between 20-25 (Developing Trend)
            if curr_plus > curr_minus:
                decision = "HOLD"
            else:
                decision = "SELL"
                
                decision = "SELL"
                
        # Divergence Check (on ADX? Hard to interpret. Returning 0)
        return decision, (curr_adx, curr_plus, curr_minus), 0

    def _calculate_ichimoku(self):
        """
        Calculates Ichimoku Cloud components.
        Returns: tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span
        """
        # Tenkan-sen (Conversion Line): (9-period High + 9-period Low) / 2
        high_9 = self.data['High'].rolling(window=9).max()
        low_9 = self.data['Low'].rolling(window=9).min()
        tenkan_sen = (high_9 + low_9) / 2

        # Kijun-sen (Base Line): (26-period High + 26-period Low) / 2
        high_26 = self.data['High'].rolling(window=26).max()
        low_26 = self.data['Low'].rolling(window=26).min()
        kijun_sen = (high_26 + low_26) / 2

        # Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2 shifted 26 periods ahead
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)

        # Senkou Span B (Leading Span B): (52-period High + 52-period Low) / 2 shifted 26 periods ahead
        high_52 = self.data['High'].rolling(window=52).max()
        low_52 = self.data['Low'].rolling(window=52).min()
        senkou_span_b = ((high_52 + low_52) / 2).shift(26)

        # Chikou Span (Lagging Span): Close shifted 26 periods behind
        # Note: In a real-time dataframe, Chikou is the current close plotted 26 bars back.
        # For analysis of the 'current' moment, we look at where Chikou WOULD be (which is just current Close)
        # relative to price 26 periods ago.
        # But standard definition usually returns a shifted series.
        chikou_span = self.data['Close'].shift(-26)

        return tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span

    def get_ichimoku_decision(self):
        """
        Returns decision based on Ichimoku Cloud.
        """
        tenkan, kijun, span_a, span_b, chikou = self._calculate_ichimoku()
        
        # We need the values at the current index (latest data point)
        # Note: Span A and B are shifted FORWARD, so 'current' index has the cloud for 'future' 
        # But standard trading checks price vs "Current Cloud" (which was projected 26 periods ago).
        # Wait, standard implementation: 
        # Span A is plotted 26 days ahead.
        # So to check Price vs Cloud TODAY, we need Span A/B values that were shifted to today.
        # The shift(26) moves NaN to the start. So the value at index `i` IS the cloud value for `i`.
        # Yes, Pandas shift(positive) pushes data forward.
        
        curr_price = self.data['Close'].iloc[-1]
        curr_tenkan = tenkan.iloc[-1]
        curr_kijun = kijun.iloc[-1]
        curr_span_a = span_a.iloc[-1]
        curr_span_b = span_b.iloc[-1]
        
        decision = "NEUTRAL"
        
        # Determine Cloud Status
        above_cloud = curr_price > curr_span_a and curr_price > curr_span_b
        below_cloud = curr_price < curr_span_a and curr_price < curr_span_b
        
        # Determine TK Cross
        # TK Cross HAPPENED implies checking previous values, but for simple status:
        tk_bullish = curr_tenkan > curr_kijun
        tk_bearish = curr_tenkan < curr_kijun
        
        if above_cloud and tk_bullish:
            decision = "STRONG BUY"
        elif below_cloud and tk_bearish:
            decision = "STRONG SELL"
        elif above_cloud:
            decision = "BUY" # or HOLD
        elif below_cloud:
            decision = "SELL" # or HOLD
        else:
            decision = "NEUTRAL" # Price inside cloud
            
            decision = "NEUTRAL" # Price inside cloud
            
        return decision, (curr_tenkan, curr_kijun, curr_span_a, curr_span_b), 0

    def _calculate_alligator(self):
        """
        Calculates Bill Williams Alligator indicator (Jaw, Teeth, Lips).
        Uses SMMA (Smoothed Moving Average).
        Returns: jaw, teeth, lips
        """
        # SMMA Helper
        def smma(series, window):
            return series.ewm(alpha=1/window, adjust=False).mean()

        hl2 = (self.data['High'] + self.data['Low']) / 2

        # Jaw (Blue): 13-period SMMA, shifted 8
        jaw = smma(hl2, 13).shift(8)

        # Teeth (Red): 8-period SMMA, shifted 5
        teeth = smma(hl2, 8).shift(5)

        # Lips (Green): 5-period SMMA, shifted 3
        lips = smma(hl2, 5).shift(3)

        return jaw, teeth, lips

    def get_alligator_decision(self):
        """
        Returns decision based on Alligator indicator.
        """
        jaw, teeth, lips = self._calculate_alligator()
        
        curr_jaw = jaw.iloc[-1]
        curr_teeth = teeth.iloc[-1]
        curr_lips = lips.iloc[-1]
        
        # Previous values for crossover check
        # Note: shift() moved data, so iloc[-2] is the previous valid point relative to iloc[-1]
        prev_jaw = jaw.iloc[-2]
        prev_teeth = teeth.iloc[-2]
        prev_lips = lips.iloc[-2]

        decision = "NEUTRAL"
        
        # 1. Feeding (Strong Trend)
        if curr_lips > curr_teeth and curr_teeth > curr_jaw:
            decision = "STRONG BUY"
        elif curr_lips < curr_teeth and curr_teeth < curr_jaw:
            decision = "STRONG SELL"
        
        # 2. Awakening (Crossovers - Signal Start)
        # If not already feeding, look for crossovers
        elif decision == "NEUTRAL":
            # Bullish Cross: Lips crossing above Teeth
            if prev_lips < prev_teeth and curr_lips > curr_teeth:
                decision = "BUY"
            # Bearish Cross: Lips crossing below Teeth
            elif prev_lips > prev_teeth and curr_lips < curr_teeth:
                decision = "SELL"
        
        # 3. Sleeping is NEUTRAL (already set default)
            
        return decision, (curr_jaw, curr_teeth, curr_lips), 0

    def _calculate_awesome(self):
        """
        Calculates Awesome Oscillator (AO).
        AO = SMA(Median Price, 5) - SMA(Median Price, 34)
        Returns: ao_series
        """
        median_price = (self.data['High'] + self.data['Low']) / 2
        sma_5 = median_price.rolling(window=5).mean()
        sma_34 = median_price.rolling(window=34).mean()
        
        ao = sma_5 - sma_34
        return ao

    def get_awesome_decision(self):
        """
        Returns decision based on Awesome Oscillator.
        """
        ao = self._calculate_awesome()
        
        curr_ao = ao.iloc[-1]
        prev_ao = ao.iloc[-2]
        
        decision = "NEUTRAL"
        
        # Zero Cross
        if prev_ao < 0 and curr_ao > 0:
            decision = "STRONG BUY"
        elif prev_ao > 0 and curr_ao < 0:
            decision = "STRONG SELL"
        # Trend State
        elif curr_ao > 0:
            if curr_ao > prev_ao:
                decision = "HOLD" # Rising in positive territory
            else:
                decision = "HOLD" # Falling but still positive (Momentum fading but trend still up)
        elif curr_ao < 0:
            if curr_ao < prev_ao:
                decision = "SELL" # Falling in negative territory
            else:
                decision = "SELL" # Rising but still negative (Selling fading but trend still down)
                
        # Divergence Check (Using Alligator Jaw/Teeth/Lips? No. Using 0)    
        # Wait, I accidentally edited get_alligator_decision instead of get_awesome_decision in previous turn? 
        # No, this is get_awesome_decision block in my mind but file has them. 
        # I need to be careful with line numbers.
        # This chunk is targeting get_awesome_decision based on context.
        
        return decision, curr_ao, self._check_divergence(ao)


    def _calculate_parabolic_sar(self, step=0.02, max_step=0.20):
        """
        Calculates Parabolic SAR.
        Returns: sar_series (pd.Series)
        """
        high = self.data['High']
        low = self.data['Low']
        close = self.data['Close']
        
        sar = np.zeros(len(close))
        
        # Initial values (assuming uptrend start for simplicity or first bar)
        # Detailed implementation of Parabolic SAR
        long_trend = True # Assume Up
        result_sar = [low.iloc[0]] # Start at low
        ep = high.iloc[0] # Extreme Point
        af = step
        
        for i in range(1, len(close)):
            prev_sar = result_sar[-1]
            
            # Calculate new SAR based on previous values
            new_sar = prev_sar + af * (ep - prev_sar)
            
            # Constraint check (SAR vs Price)
            current_high = high.iloc[i]
            current_low = low.iloc[i]
            prev_high = high.iloc[i-1]
            prev_low = low.iloc[i-1]
            
            if long_trend:
                # Uptrend Constraints: SAR cannot be above Current Low or Previous Low
                if new_sar > prev_low: new_sar = prev_low 
                if new_sar > current_low: new_sar = current_low
                
                # Check for Reversal
                if current_low < new_sar:
                    long_trend = False
                    new_sar = ep # Reversal SAR is the old EP
                    ep = current_low # Reset EP to new low
                    af = step # Reset AF
                else:
                    # Continue Uptrend
                    if current_high > ep:
                        ep = current_high
                        af = min(af + step, max_step)
            else:
                # Downtrend Constraints: SAR cannot be below Current High or Previous High
                if new_sar < prev_high: new_sar = prev_high
                if new_sar < current_high: new_sar = current_high
                
                # Check for Reversal
                if current_high > new_sar:
                    long_trend = True
                    new_sar = ep # Reversal SAR is the old EP
                    ep = current_high # Reset EP to new high
                    af = step # Reset AF
                else:
                    # Continue Downtrend
                    if current_low < ep:
                        ep = current_low
                        af = min(af + step, max_step)
                        
            result_sar.append(new_sar)
            
        return pd.Series(result_sar, index=self.data.index)

    def get_sar_decision(self):
        """
        Returns decision based on Parabolic SAR.
        """
        sar = self._calculate_parabolic_sar()
        
        current_price = self.data['Close'].iloc[-1]
        current_sar = sar.iloc[-1]
        
        prev_price = self.data['Close'].iloc[-2]
        prev_sar = sar.iloc[-2]
        
        decision = "HOLD"
        
        # Check for Reversals (Crossovers)
        if prev_price < prev_sar and current_price > current_sar:
            decision = "STRONG BUY"
        elif prev_price > prev_sar and current_price < current_sar:
            decision = "STRONG SELL"
        # Trend Status
        elif current_price > current_sar:
            decision = "HOLD"
        elif current_price < current_sar:
             decision = "SELL"
             
             
        return decision, current_sar, 0

    def _calculate_volume_ma(self, window=20):
        """
        Calculates Volume Moving Average.
        """
        return self.data['Volume'].rolling(window=window).mean()

    def _calculate_mfi(self, window=14):
        """
        Calculates Money Flow Index (MFI).
        Returns: mfi_series
        """
        typical_price = (self.data['High'] + self.data['Low'] + self.data['Close']) / 3
        raw_money_flow = typical_price * self.data['Volume']
        
        # Shift typical price to compare with previous
        prev_tp = typical_price.shift(1)
        
        pos_flow = pd.Series(0.0, index=self.data.index)
        neg_flow = pd.Series(0.0, index=self.data.index)
        
        # Vectorized assignment
        pos_flow[typical_price > prev_tp] = raw_money_flow[typical_price > prev_tp]
        neg_flow[typical_price < prev_tp] = raw_money_flow[typical_price < prev_tp]
        
        # Calculate Ratio
        positive_mf_sum = pos_flow.rolling(window=window).sum()
        negative_mf_sum = neg_flow.rolling(window=window).sum()
        
        # Avoid division by zero
        money_ratio = positive_mf_sum / negative_mf_sum
        
        mfi = 100 - (100 / (1 + money_ratio))
        return mfi

    def get_mfi_decision(self):
        """
        Returns decision based on MFI.
        """
        mfi = self._calculate_mfi()
        curr_mfi = mfi.iloc[-1]
        
        decision = "NEUTRAL"
        
        if curr_mfi < 20:
            decision = "BUY" # Oversold
        elif curr_mfi > 80:
            decision = "SELL" # Overbought
        elif curr_mfi > 50:
            decision = "HOLD" # Bullish pressure
        else:
            decision = "NEUTRAL" # Bearish pressure
        
        # Divergence Check (on MFI)
        div = self._check_divergence(mfi)
            
        return decision, curr_mfi, div

    def _calculate_cmf(self, window=20):
        """
        Calculates Chaikin Money Flow (CMF).
        Returns: cmf_series
        """
        close = self.data['Close']
        high = self.data['High']
        low = self.data['Low']
        volume = self.data['Volume']
        
        # Money Flow Multiplier
        # ( (Close - Low) - (High - Close) ) / (High - Low)
        # Avoid division by zero
        high_low = high - low
        mfm = ((close - low) - (high - close)) / high_low
        mfm = mfm.fillna(0.0) # If High == Low
        
        # Money Flow Volume
        mfv = mfm * volume
        
        # CMF = Sum(MFV, 20) / Sum(Volume, 20)
        cmf = mfv.rolling(window=window).sum() / volume.rolling(window=window).sum()
        
        return cmf

    def get_cmf_decision(self):
        """
        Returns decision based on CMF.
        """
        cmf = self._calculate_cmf()
        curr_cmf = cmf.iloc[-1]
        
        decision = "NEUTRAL"
        
        if curr_cmf > 0.05:
            decision = "BUY"
        elif curr_cmf < -0.05:
            decision = "SELL"
        else:
            decision = "HOLD"
            
        # Divergence Check
        div = self._check_divergence(cmf)
        
        return decision, curr_cmf, div

    def _calculate_wavetrend(self, n1=10, n2=21):
        """
        Calculates WaveTrend Oscillator.
        Returns: wt1 (WaveTrend), wt2 (Signal)
        """
        ap = (self.data['High'] + self.data['Low'] + self.data['Close']) / 3
        
        # ESA = EMA(AP, n1)
        esa = ap.ewm(span=n1, adjust=False).mean()
        
        # D = EMA(Abs(AP - ESA), n1)
        d = (ap - esa).abs().ewm(span=n1, adjust=False).mean()
        
        # CI = (AP - ESA) / (0.015 * D)
        # Avoid division by zero
        ci = (ap - esa) / (0.015 * d)
        ci = ci.fillna(0.0)
        
        # WT1 (WaveTrend) = EMA(CI, n2)
        wt1 = ci.ewm(span=n2, adjust=False).mean()
        
        # WT2 (Signal) = SMA(WT1, 4)
        wt2 = wt1.rolling(window=4).mean()
        
        return wt1, wt2

    def get_wavetrend_decision(self):
        """
        Returns decision based on WaveTrend.
        """
        wt1, wt2 = self._calculate_wavetrend()
        
        curr_wt1 = wt1.iloc[-1]
        curr_wt2 = wt2.iloc[-1]
        prev_wt1 = wt1.iloc[-2]
        prev_wt2 = wt2.iloc[-2]
        
        decision = "HOLD"
        
        # Crossovers
        bullish_cross = prev_wt1 < prev_wt2 and curr_wt1 > curr_wt2
        bearish_cross = prev_wt1 > prev_wt2 and curr_wt1 < curr_wt2
        
        if bullish_cross:
            if curr_wt1 < -50:
                decision = "STRONG BUY" # Oversold Cross
            else:
                decision = "BUY"
        elif bearish_cross:
            if curr_wt1 > 50:
                decision = "STRONG SELL" # Overbought Cross
            else:
                decision = "SELL"
        # Trend Hold
        elif curr_wt1 > curr_wt2:
            decision = "HOLD" # Bullish
        elif curr_wt1 < curr_wt2:
            decision = "SELL" # Bearish
            
        # Divergence Check (on WT1)
        div = self._check_divergence(wt1)
        
        return decision, (curr_wt1, curr_wt2), div

    def _calculate_kama(self, n=10, pow1=2, pow2=30):
        """
        Calculates Kaufman Adaptive Moving Average (KAMA).
        Returns: kama_series
        """
        close = self.data['Close']
        
        # Change = Abs(Price - Price(n))
        change = (close - close.shift(n)).abs()
        
        # Volatility = Sum(Abs(Price - Price(1)), n)
        volatility = (close - close.shift(1)).abs().rolling(window=n).sum()
        
        # Efficiency Ratio (ER)
        # Avoid division by zero
        er = change / volatility
        er = er.fillna(0.0)
        
        # Smoothing Constant (SC)
        # fast_sc = 2 / (pow1 + 1)
        # slow_sc = 2 / (pow2 + 1)
        fast_sc = 2 / (pow1 + 1)
        slow_sc = 2 / (pow2 + 1)
        
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        
        # KAMA Calculation
        # KAMA = PrevKAMA + SC * (Price - PrevKAMA)
        # Initialize KAMA with Simple Moving Average for the first valid point
        # or just the first close price.
        
        kama = [np.nan] * len(close)
        
        # Start from n-1 (since we need n periods for ER)
        # But rolling sum produces NaN for first n-1 indices (0 to n-2).
        # First valid index is n-1.
        first_valid_idx = n
        
        if first_valid_idx < len(close):
            kama[first_valid_idx-1] = close.iloc[first_valid_idx-1] # Initialize with Price
            
            for i in range(first_valid_idx, len(close)):
                kama[i] = kama[i-1] + sc.iloc[i] * (close.iloc[i] - kama[i-1])
                
        return pd.Series(kama, index=self.data.index)

    def get_kama_decision(self):
        """
        Returns decision based on KAMA.
        """
        kama = self._calculate_kama()
        
        curr_price = self.data['Close'].iloc[-1]
        curr_kama = kama.iloc[-1]
        prev_kama = kama.iloc[-2]
        
        decision = "HOLD"
        
        is_rising = curr_kama > prev_kama
        is_falling = curr_kama < prev_kama
        
        if curr_price > curr_kama:
            if is_rising:
                decision = "STRONG BUY"
            else:
                decision = "BUY" # Price above, but KAMA flat/falling (Pullback?)
        elif curr_price < curr_kama:
            if is_falling:
                decision = "STRONG SELL"
            else:
                decision = "SELL" # Price below, but KAMA flat/rising
                
        # Divergence Check (Does not apply well to MA, typically returning 0)
        # But we can check if Price makes HH and KAMA makes LH? No, KAMA follows price.
        # Divergence is usually for Oscillators.
        
        return decision, curr_kama, 0

    def _calculate_gator(self):
        """
        Calculates Gator Oscillator.
        Returns: upper_bar, lower_bar (absolute values)
        """
        # Reuse Alligator components
        jaw, teeth, lips = self._calculate_alligator()
        
        # Upper Bar: |Jaw - Teeth|
        upper_bar = (jaw - teeth).abs()
        
        # Lower Bar: |Teeth - Lips|
        lower_bar = (teeth - lips).abs()
        
        return upper_bar, lower_bar

    def get_gator_decision(self):
        """
        Returns decision based on Gator Oscillator Phases.
        """
        upper, lower = self._calculate_gator()
        
        curr_upper = upper.iloc[-1]
        curr_lower = lower.iloc[-1]
        
        prev_upper = upper.iloc[-2]
        prev_lower = lower.iloc[-2]
        
        decision = "NEUTRAL"
        
        # Determine Phase
        upper_expanding = curr_upper > prev_upper
        lower_expanding = curr_lower > prev_lower
        
        if not upper_expanding and not lower_expanding:
            phase = "SLEEPING"
        elif (upper_expanding and not lower_expanding) or (not upper_expanding and lower_expanding):
            phase = "AWAKENING"
        elif upper_expanding and lower_expanding:
            phase = "EATING"
        else:
            phase = "SATED" # Should be covered by awakening logic actually (one reducing), 
            # but specifically: if we were eating and now one reduces.
            pass
            
        # Decision Logic based on Alligator Trend
        # We need Alligator Trend Direction to know if it's Buy or Sell
        # Gator only tells us the STRENGTH/PHASE, not direction.
        # But we can infer direction from Alligator lines or pass it.
        # Let's recalculate basic direction
        jaw, teeth, lips = self._calculate_alligator()
        curr_jaw = jaw.iloc[-1]
        curr_teeth = teeth.iloc[-1]
        curr_lips = lips.iloc[-1]
        
        is_uptrend = curr_lips > curr_teeth and curr_teeth > curr_jaw
        is_downtrend = curr_lips < curr_teeth and curr_teeth < curr_jaw
        
        if phase == "EATING":
            if is_uptrend:
                decision = "STRONG BUY"
            elif is_downtrend:
                decision = "STRONG SELL"
            else:
                decision = "BUY" # Volatility expansion but lines not fully aligned yet
        elif phase == "AWAKENING":
             if is_uptrend:
                decision = "BUY"
             elif is_downtrend:
                decision = "SELL"
             else:
                decision = "WAIT"
        elif phase == "SLEEPING":
            decision = "NEUTRAL"
            
        return decision, f"{phase}", 0

    def _calculate_demand_index(self, window=20):
        """
        Calculates Demand Index (Buying vs Selling Pressure).
        Returns: di_series
        """
        close = self.data['Close']
        volume = self.data['Volume']
        prev_close = close.shift(1)
        
        # Buying Pressure (BP)
        bp = pd.Series(0.0, index=close.index)
        bp[close > prev_close] = volume[close > prev_close]
        
        # Selling Pressure (SP)
        sp = pd.Series(0.0, index=close.index)
        sp[close < prev_close] = volume[close < prev_close]
        
        # Smoothing (EMA)
        bp_ema = bp.ewm(span=window, adjust=False).mean()
        sp_ema = sp.ewm(span=window, adjust=False).mean()
        vol_ema = volume.ewm(span=window, adjust=False).mean()
        
        # Demand Index formula: 100 * (BP - SP) / Vol_EMA
        # Avoid division by zero
        di = 100 * (bp_ema - sp_ema) / vol_ema
        di = di.fillna(0.0)
        
        return di

    def get_demand_index_decision(self):
        """
        Returns decision based on Demand Index.
        """
        di = self._calculate_demand_index()
        curr_di = di.iloc[-1]
        
        decision = "HOLD"
        
        if curr_di > 0:
            decision = "BUY" # Buying Pressure > Selling Pressure
        elif curr_di < 0:
            decision = "SELL" # Selling Pressure > Buying Pressure
            
        # Refine decision based on strength?
        # Maybe > 20 is Strong Buy? For now keep simple zero cross.
        
        # Divergence Check
        div = self._check_divergence(di)
        
        return decision, curr_di, div

    def _calculate_williams_r(self, window=14):
        """
        Calculates Williams %R.
        Returns: wr_series (0 to -100)
        """
        close = self.data['Close']
        high = self.data['High']
        low = self.data['Low']
        
        # Highest High in window
        hh = high.rolling(window=window).max()
        # Lowest Low in window
        ll = low.rolling(window=window).min()
        
        # %R = (Highest High - Close) / (Highest High - Lowest Low) * -100
        # Avoid division by zero
        wr = (hh - close) / (hh - ll) * -100
        wr = wr.fillna(0.0) # Or handle appropriately
        
        return wr

    def get_williams_r_decision(self):
        """
        Returns decision based on Williams %R.
        """
        wr = self._calculate_williams_r()
        curr_wr = wr.iloc[-1]
        
        decision = "HOLD"
        
        if curr_wr > -20:
             decision = "SELL" # Overbought (0 to -20)
        elif curr_wr < -80:
             decision = "BUY" # Oversold (-80 to -100)
             
        # Divergence Check
        div = self._check_divergence(wr)
        
        return decision, curr_wr, div

    def _calculate_aroon(self, window=25):
        """
        Calculates Aroon Indicator (Up, Down, Oscillator).
        Returns: aroon_up, aroon_down, aroon_osc
        """
        high = self.data['High']
        low = self.data['Low']
        
        aroon_up = []
        aroon_down = []
        
        # Iterate to find days since high/low
        # Rolling apply is slow, loop might be clearer or use rolling argmax
        
        # We can use rolling argmax to find the index of max within window
        # But we need 'days since', not absolute index.
        # Efficient way:
        
        for i in range(len(high)):
            if i < window - 1:
                aroon_up.append(np.nan)
                aroon_down.append(np.nan)
                continue
                
            window_high = high.iloc[i-window+1:i+1]
            window_low = low.iloc[i-window+1:i+1]
            
            # Days since high (0 to window-1)
            # argmax returns offset from start of window
            days_since_high = (window - 1) - window_high.argmax()
            days_since_low = (window - 1) - window_low.argmin()
            
            up = ((window - days_since_high) / window) * 100
            down = ((window - days_since_low) / window) * 100
            
            aroon_up.append(up)
            aroon_down.append(down)
            
        aroon_up = pd.Series(aroon_up, index=self.data.index)
        aroon_down = pd.Series(aroon_down, index=self.data.index)
        aroon_osc = aroon_up - aroon_down
        
        return aroon_up, aroon_down, aroon_osc

    def get_aroon_decision(self):
        """
        Returns decision based on Aroon.
        """
        up, down, osc = self._calculate_aroon()
        
        curr_up = up.iloc[-1]
        curr_down = down.iloc[-1]
        curr_osc = osc.iloc[-1]
        
        decision = "NEUTRAL"
        
        if curr_up > 70 and curr_down < 30:
            decision = "STRONG BUY"
        elif curr_down > 70 and curr_up < 30:
            decision = "STRONG SELL"
        elif curr_up > curr_down:
            decision = "BUY"
        elif curr_down > curr_up:
            decision = "SELL"
            
        # Divergence Check (on Oscillator)
        div = self._check_divergence(osc)
        
        return decision, curr_osc, div

    def _calculate_dema(self, series, window):
        """
        Calculates Double Exponential Moving Average (DEMA).
        Formula: 2 * EMA - EMA(EMA)
        """
        ema1 = series.ewm(span=window, adjust=False).mean()
        ema2 = ema1.ewm(span=window, adjust=False).mean()
        dema = 2 * ema1 - ema2
        return dema

    def get_dema_decision(self):
        """
        Returns decision based on DEMA Crossovers.
        """
        if self.horizon == 'short':
             short_window, long_window = 9, 21
        else:
             short_window, long_window = 50, 200
             
        close = self.data['Close']
        fast_dema = self._calculate_dema(close, short_window)
        slow_dema = self._calculate_dema(close, long_window)
        
        curr_fast = fast_dema.iloc[-1]
        curr_slow = slow_dema.iloc[-1]
        prev_fast = fast_dema.iloc[-2]
        prev_slow = slow_dema.iloc[-2]
        
        decision = "HOLD"
        
        # Crossovers
        if prev_fast < prev_slow and curr_fast > curr_slow:
            decision = "STRONG BUY"
        elif prev_fast > prev_slow and curr_fast < curr_slow:
            decision = "STRONG SELL"
        # Trend
        elif curr_fast > curr_slow:
            decision = "BUY"
        elif curr_fast < curr_slow:
            decision = "SELL"
            
        return decision, (curr_fast, curr_slow), 0

    def _calculate_median_indicator(self, window=20):
        """
        Calculates Rolling Median of (High + Low) / 2.
        """
        mid_price = (self.data['High'] + self.data['Low']) / 2
        median = mid_price.rolling(window=window).median()
        return median

    def get_median_decision(self):
        """
        Returns decision based on Price vs Rolling Median.
        """
        median = self._calculate_median_indicator()
        curr_median = median.iloc[-1]
        close = self.data['Close'].iloc[-1]
        
        decision = "HOLD"
        
        if close > curr_median:
            decision = "BUY"
        elif close < curr_median:
            decision = "SELL"
            
        # Optional: Add buffer/hysteresis logic here if needed
        
        # Divergence Check? Not typical for Median itself (it's a price overlay), 
        # but we can check if price is making higher highs while median is flat? 
        # For now, return 0 for divergence.
        
        return decision, curr_median, 0

    def _calculate_fisher(self, window=9):
        """
        Calculates Ehlers Fisher Transform.
        Returns: fisher_series, trigger_series
        """
        high = self.data['High']
        low = self.data['Low']
        mid_price = (high + low) / 2
        n = len(mid_price)
        
        fisher = np.zeros(n)
        trigger = np.zeros(n)
        value = np.zeros(n)
        
        # Calculate MaxH and MinL over window
        # We can use rolling functionalities for efficiency
        period_high = high.rolling(window=window).max().bfill() # Use bfill to avoid NaNs at start messing up loop too much
        period_low = low.rolling(window=window).min().bfill()
        
        for i in range(1, n):
            # Avoid division by zero
            denom = period_high.iloc[i] - period_low.iloc[i]
            if denom == 0:
                denom = 0.001
            
            # Normalize price to -1 to 1
            # Ehlers formula: 0.33 * 2 * ((Mid - Min) / (Max - Min) - 0.5) + 0.67 * PrevValue
            val = 0.33 * 2 * ((mid_price.iloc[i] - period_low.iloc[i]) / denom - 0.5) + 0.67 * value[i-1]
            
            # Limit value to -0.999 to 0.999 to avoid Inf in Log
            if val > 0.99:
                val = 0.999
            elif val < -0.99:
                val = -0.999
            
            value[i] = val
            
            # Fisher Transform
            # Fisher = 0.5 * ln((1 + Value) / (1 - Value)) + 0.5 * PrevFisher
            fisher[i] = 0.5 * np.log((1 + val) / (1 - val)) + 0.5 * fisher[i-1]
            trigger[i] = fisher[i-1]
            
        return pd.Series(fisher, index=self.data.index), pd.Series(trigger, index=self.data.index)

    def get_fisher_decision(self):
        """
        Returns decision based on Fisher Transform.
        """
        fisher, trigger = self._calculate_fisher()
        
        curr_fisher = fisher.iloc[-1]
        curr_trigger = trigger.iloc[-1]
        prev_fisher = fisher.iloc[-2]
        prev_trigger = trigger.iloc[-2]
        
        decision = "HOLD"
        
        # Crossovers
        if prev_fisher < prev_trigger and curr_fisher > curr_trigger:
            decision = "BUY"
        elif prev_fisher > prev_trigger and curr_fisher < curr_trigger:
            decision = "SELL"
            
        # Extreme Value Checks (Reversal Warning)
        if curr_fisher > 2.0:
            # Overbought condition
             if decision == "BUY": # Trying to buy at extreme top?
                 decision = "HOLD" # Or WAIT
        elif curr_fisher < -2.0:
            # Oversold condition
             if decision == "SELL": # Trying to sell at extreme bottom?
                 decision = "HOLD"
                 
        # Divergence Check
        div = self._check_divergence(fisher) # Divergence on Fisher line
        
        return decision, curr_fisher, div

    def get_volume_info(self):
        """
        Returns Volume information (Current Volume, Volume Ratio).
        """
        current_volume = self.data['Volume'].iloc[-1]
        volume_ma = self._calculate_volume_ma()
        current_volume_ma = volume_ma.iloc[-1]
        
        # Avoid division by zero
        if current_volume_ma > 0:
            volume_ratio = current_volume / current_volume_ma
        else:
            volume_ratio = 1.0
            
        return int(current_volume), round(volume_ratio, 2)

    def get_indicator_decisions(self, *indicators):
        """
        Aggregates decisions from multiple indicators into a DataFrame.
        Usage: stock.get_indicator_decisions("RSI", "MACD", "BB", "MA", "DMI", "SAR")
        """
        results = []
        
        for indicator in indicators:
            indicator = indicator.upper()
            indicator = indicator.upper()
            if indicator == "RSI":
                decision, value, div = self.get_rsi_decision()
                results.append({"Indicator": "RSI", "Decision": decision, "Value": f"{value:.2f}", "Divergence": div})
            elif indicator == "MACD":
                decision, (macd_val, sig_val), div = self.get_macd_decision()
                print_val = f"MACD:{macd_val:.2f}" # Shortened for display
                results.append({"Indicator": "MACD", "Decision": decision, "Value": f"MACD:{macd_val:.2f}", "Divergence": div})
            elif indicator == "BB":
                decision, (price, lower, upper), div = self.get_bollinger_decision()
                results.append({"Indicator": "BB", "Decision": decision, "Value": f"P:{price:.2f}", "Divergence": div})
            elif indicator == "MA":
                decision, (short_ma, long_ma), div = self.get_ma_decision()
                results.append({"Indicator": "MA", "Decision": decision, "Value": f"S:{short_ma:.2f}", "Divergence": div})
            elif indicator == "DMI":
                decision, (adx, p_di, m_di), div = self.get_dmi_decision()
                results.append({"Indicator": "DMI", "Decision": decision, "Value": f"ADX:{adx:.2f}", "Divergence": div})
            elif indicator == "SAR":
                decision, sar_val, div = self.get_sar_decision()
                results.append({"Indicator": "SAR", "Decision": decision, "Value": f"{sar_val:.2f}", "Divergence": div})
            elif indicator == "STOCH":
                decision, (k, d), div = self.get_stoch_decision()
                results.append({"Indicator": "STOCH", "Decision": decision, "Value": f"K:{k:.2f}", "Divergence": div})
            elif indicator == "STOCHRSI":
                decision, (k, d), div = self.get_stochrsi_decision()
                results.append({"Indicator": "STOCHRSI", "Decision": decision, "Value": f"K:{k:.2f}", "Divergence": div})
            elif indicator == "SUPERTREND":
                decision, (st, trend), div = self.get_supertrend_decision()
                results.append({"Indicator": "SUPERTREND", "Decision": decision, "Value": f"ST:{st:.2f}", "Divergence": div})
            elif indicator == "ICHIMOKU":
                decision, (tenkan, kijun, sa, sb), div = self.get_ichimoku_decision()
                results.append({"Indicator": "ICHIMOKU", "Decision": decision, "Value": f"T:{tenkan:.2f}", "Divergence": div})
            elif indicator == "ALLIGATOR":
                decision, (jaw, teeth, lips), div = self.get_alligator_decision()
                results.append({"Indicator": "ALLIGATOR", "Decision": decision, "Value": f"L:{lips:.2f}", "Divergence": div})
            elif indicator == "AWESOME":
                decision, ao_val, div = self.get_awesome_decision()
                results.append({"Indicator": "AWESOME", "Decision": decision, "Value": f"{ao_val:.2f}", "Divergence": div})
            elif indicator == "MFI":
                decision, mfi_val, div = self.get_mfi_decision()
                results.append({"Indicator": "MFI", "Decision": decision, "Value": f"{mfi_val:.2f}", "Divergence": div})
            elif indicator == "CMF":
                decision, cmf_val, div = self.get_cmf_decision()
                results.append({"Indicator": "CMF", "Decision": decision, "Value": f"{cmf_val:.2f}", "Divergence": div})
            elif indicator == "WAVETREND":
                decision, (wt1, wt2), div = self.get_wavetrend_decision()
                results.append({"Indicator": "WAVETREND", "Decision": decision, "Value": f"WT:{wt1:.2f}", "Divergence": div})
            elif indicator == "KAMA":
                decision, kama_val, div = self.get_kama_decision()
                results.append({"Indicator": "KAMA", "Decision": decision, "Value": f"{kama_val:.2f}", "Divergence": div})
            elif indicator == "GATOR":
                decision, phase, div = self.get_gator_decision()
                results.append({"Indicator": "GATOR", "Decision": decision, "Value": f"{phase}", "Divergence": div})
            elif indicator == "DEMAND_INDEX":
                decision, di_val, div = self.get_demand_index_decision()
                results.append({"Indicator": "DEMAND_INDEX", "Decision": decision, "Value": f"{di_val:.2f}", "Divergence": div})
            elif indicator == "WILLIAMS_R":
                decision, wr_val, div = self.get_williams_r_decision()
                results.append({"Indicator": "WILLIAMS_R", "Decision": decision, "Value": f"{wr_val:.2f}", "Divergence": div})
            elif indicator == "AROON":
                decision, osc_val, div = self.get_aroon_decision()
                results.append({"Indicator": "AROON", "Decision": decision, "Value": f"Osc:{osc_val:.2f}", "Divergence": div})
            elif indicator == "DEMA":
                decision, (fast, slow), div = self.get_dema_decision()
                results.append({"Indicator": "DEMA", "Decision": decision, "Value": f"F:{fast:.2f}", "Divergence": div})
            elif indicator == "MEDIAN":
                decision, med_val, div = self.get_median_decision()
                results.append({"Indicator": "MEDIAN", "Decision": decision, "Value": f"{med_val:.2f}", "Divergence": div})
            elif indicator == "FISHER":
                decision, fisher_val, div = self.get_fisher_decision()
                results.append({"Indicator": "FISHER", "Decision": decision, "Value": f"F:{fisher_val:.2f}", "Divergence": div})
            elif indicator == "VWAP":
                decision, (vwap_val, _), div = self.get_vwap_decision()
                results.append({"Indicator": "VWAP", "Decision": decision, "Value": f"{vwap_val:.2f}", "Divergence": div})
            elif indicator == "OBV":
                decision, (obv_val, obv_ma), div = self.get_obv_decision()
                results.append({"Indicator": "OBV", "Decision": decision, "Value": f"{obv_val:.0f}", "Divergence": div})
            elif indicator == "CCI":
                decision, (cci_val, _), div = self.get_cci_decision()
                results.append({"Indicator": "CCI", "Decision": decision, "Value": f"{cci_val:.2f}", "Divergence": div})
            else:
                results.append({"Indicator": indicator, "Decision": "UNKNOWN", "Value": "N/A", "Divergence": 0})
        
        return pd.DataFrame(results)

    def _calculate_stochastic(self, k_window=14, d_window=3):
        """
        Calculates Stochastic Oscillator (%K and %D).
        Returns: k_percent, d_percent
        """
        low_min = self.data['Low'].rolling(window=k_window).min()
        high_max = self.data['High'].rolling(window=k_window).max()
        
        k_percent = 100 * ((self.data['Close'] - low_min) / (high_max - low_min))
        d_percent = k_percent.rolling(window=d_window).mean()
        
        return k_percent, d_percent

    def get_stoch_decision(self):
        """
        Returns decision based on Stochastic Oscillator.
        """
        k, d = self._calculate_stochastic()
        
        curr_k = k.iloc[-1]
        curr_d = d.iloc[-1]
        prev_k = k.iloc[-2]
        prev_d = d.iloc[-2]
        
        decision = "HOLD"
        
        # Crossovers
        if prev_k < prev_d and curr_k > curr_d:
            if curr_k < 20: decision = "BUY"
            else: decision = "HOLD"
        elif prev_k > prev_d and curr_k < curr_d:
            if curr_k > 80: decision = "SELL"
            else: decision = "SELL"
        # Trend
        elif curr_k > curr_d:
            decision = "HOLD"
        elif curr_k < curr_d:
            decision = "SELL"
            
        # Divergence Check
        div = self._check_divergence(k)
        return decision, (curr_k, curr_d), div

    def _calculate_stochrsi(self, window=14, smooth_k=3, smooth_d=3):
        """
        Calculates Stochastic RSI.
        Returns: k_percent, d_percent
        """
        rsi = self._calculate_rsi(window=window)
        
        rsi_min = rsi.rolling(window=window).min()
        rsi_max = rsi.rolling(window=window).max()
        
        stoch_rsi = 100 * ((rsi - rsi_min) / (rsi_max - rsi_min))
        
        k_percent = stoch_rsi.rolling(window=smooth_k).mean()
        d_percent = k_percent.rolling(window=smooth_d).mean()
        
        return k_percent, d_percent

    def get_stochrsi_decision(self):
        """
        Returns decision based on Stochastic RSI.
        """
        k, d = self._calculate_stochrsi()
        
        curr_k = k.iloc[-1]
        curr_d = d.iloc[-1]
        prev_k = k.iloc[-2]
        prev_d = d.iloc[-2]
        
        decision = "HOLD"
        
        # Crossovers
        if prev_k < prev_d and curr_k > curr_d:
            if curr_k < 20: decision = "BUY"
            else: decision = "HOLD"
        elif prev_k > prev_d and curr_k < curr_d:
            if curr_k > 80: decision = "SELL"
            else: decision = "SELL"
        # Trend
        elif curr_k > curr_d:
            decision = "HOLD"
        elif curr_k < curr_d:
            decision = "SELL"
            
        # Divergence Check
        div = self._check_divergence(k)
        return decision, (curr_k, curr_d), div

    def _calculate_vwap(self):
        """
        Calculates Intraday VWAP (Volume Weighted Average Price).
        Resets daily based on date index.
        """
        df = self.data.copy()
        # Typical Price
        df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['TPV'] = df['TP'] * df['Volume']
        
        # Group by Date to reset accumulation
        cum_tpv = df.groupby(df.index.date)['TPV'].cumsum()
        cum_vol = df.groupby(df.index.date)['Volume'].cumsum()
        
        vwap = cum_tpv / cum_vol
        return vwap

    def _calculate_obv(self):
        """
        Calculates On-Balance Volume (OBV).
        """
        change = self.data['Close'].diff()
        direction = np.zeros(len(change))
        direction[change > 0] = 1
        direction[change < 0] = -1
        
        obv = (direction * self.data['Volume']).cumsum()
        return obv

    def _calculate_cci(self, window=20):
        """
        Calculates Commodity Channel Index (CCI).
        """
        tp = (self.data['High'] + self.data['Low'] + self.data['Close']) / 3
        sma_tp = tp.rolling(window).mean()
        # Mean Absolute Deviation
        mad = tp.rolling(window).apply(lambda x: np.abs(x - x.mean()).mean())
        
        cci = (tp - sma_tp) / (0.015 * mad)
        return cci

    def _calculate_atr(self, period=10):
        """
        Calculates Average True Range (ATR).
        Returns: atr_series
        """
        high = self.data['High']
        low = self.data['Low']
        close = self.data['Close']
        
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        return atr

    def _calculate_supertrend(self, period=10, multiplier=3):
        """
        Calculates SuperTrend.
        Returns: supertrend (series), trend (series: 1=Up, -1=Down)
        """
        high = self.data['High']
        low = self.data['Low']
        close = self.data['Close']
        atr = self._calculate_atr(period=period)
        
        # Calculate Basic Upper and Lower Bands
        hl2 = (high + low) / 2
        basic_upper = hl2 + (multiplier * atr)
        basic_lower = hl2 - (multiplier * atr)
        
        # Initialize Final Bands and Trend
        # We start with NaNs to indicate no data
        final_upper = [np.nan] * len(close)
        final_lower = [np.nan] * len(close)
        trend = [1] * len(close) 
        supertrend = [np.nan] * len(close)
        
        # Start loop where ATR is valid
        # ATR valid from 'period' index (0-based) because rolling window=period needs previous data? 
        # Actually rolling mean will have first 'period-1' as NaN. So index 'period-1' is the first valid, but we need previous values for SuperTrend.
        # Let's start safely from 'period'.
        
        for i in range(period, len(close)):
            # Handle first valid value initialization
            if np.isnan(final_upper[i-1]):
                final_upper[i] = basic_upper.iloc[i]
                final_lower[i] = basic_lower.iloc[i]
                continue

            # Final Upper Band
            if basic_upper.iloc[i] < final_upper[i-1] or close.iloc[i-1] > final_upper[i-1]:
                final_upper[i] = basic_upper.iloc[i]
            else:
                final_upper[i] = final_upper[i-1]
                
            # Final Lower Band
            if basic_lower.iloc[i] > final_lower[i-1] or close.iloc[i-1] < final_lower[i-1]:
                final_lower[i] = basic_lower.iloc[i]
            else:
                final_lower[i] = final_lower[i-1]
                
            # Determine Trend
            prev_trend = trend[i-1]
            if prev_trend == 1: # Was Up
                if close.iloc[i] < final_lower[i-1]: # Breakdown
                    trend[i] = -1
                else:
                    trend[i] = 1
            else: # Was Down
                if close.iloc[i] > final_upper[i-1]: # Breakout
                    trend[i] = 1
                else:
                    trend[i] = -1
            
            # Set SuperTrend Value
            if trend[i] == 1:
                supertrend[i] = final_lower[i]
            else:
                supertrend[i] = final_upper[i]
                
        return pd.Series(supertrend, index=self.data.index), pd.Series(trend, index=self.data.index)

    def get_supertrend_decision(self):
        """
        Returns decision based on SuperTrend.
        """
        st, trend = self._calculate_supertrend()
        
        curr_price = self.data['Close'].iloc[-1]
        curr_st = st.iloc[-1]
        curr_trend = trend.iloc[-1]
        
        prev_trend = trend.iloc[-2]
        
        decision = "NEUTRAL"
        
        # Reversal (Trend Change)
        if prev_trend == -1 and curr_trend == 1:
            decision = "STRONG BUY"
        elif prev_trend == 1 and curr_trend == -1:
            decision = "STRONG SELL"
        # Trend State
        elif curr_trend == 1:
            decision = "HOLD"
        elif curr_trend == -1:
            decision = "SELL"
            
        return decision, (curr_st, "UP" if curr_trend == 1 else "DOWN"), 0

    def _calculate_sma(self, window):
        """
        Calculates Simple Moving Average (SMA).
        """
        return self.data['Close'].rolling(window=window).mean()

    def get_ma_decision(self):
        """
        Returns BUY/SELL/HOLD decision based on Moving Averages.
        
        Horizon Settings:
        - Short: 9 (Short) / 21 (Long)
        - Medium/Long: 50 (Short) / 200 (Long)
        
        Logic:
        - Golden Cross (Short > Long) & Prev (Short < Long) -> STRONG BUY
        - Death Cross (Short < Long) & Prev (Short > Long) -> STRONG SELL
        - Price > Short MA -> BUY (Trend)
        - Price < Short MA -> SELL (Trend)
        """
        if self.horizon == 'short':
             short_window, long_window = 9, 21
        else:
             short_window, long_window = 50, 200
             
        short_ma = self._calculate_sma(short_window)
        long_ma = self._calculate_sma(long_window)
        
        current_price = self.data['Close'].iloc[-1]
        curr_short = short_ma.iloc[-1]
        curr_long = long_ma.iloc[-1]
        
        prev_short = short_ma.iloc[-2]
        prev_long = long_ma.iloc[-2]
        
        decision = "HOLD"
        
        # Crossover Checks
        if prev_short < prev_long and curr_short > curr_long:
            decision = "STRONG BUY"
        elif prev_short > prev_long and curr_short < curr_long:
            decision = "STRONG SELL"
        # Trend Checks
        elif current_price > curr_short:
             decision = "HOLD"
        elif current_price < curr_short:
             decision = "SELL"
             
             
        return decision, (curr_short, curr_long), 0

    def get_vwap_decision(self):
        """
        Returns decision based on VWAP.
        Price > VWAP -> BUY (Bullish Trend)
        Price < VWAP -> SELL (Bearish Trend)
        """
        vwap = self._calculate_vwap()
        current_price = self.data['Close'].iloc[-1]
        current_vwap = vwap.iloc[-1]
        
        if current_price > current_vwap:
            decision = "BUY"
        else:
            decision = "SELL"
            
        return decision, (current_vwap, 0), 0

    def get_obv_decision(self):
        """
        Returns decision based on OBV.
        Using 20-period MA crossover logic.
        """
        obv = self._calculate_obv()
        obv_ma = obv.rolling(window=20).mean()
        
        curr_obv = obv.iloc[-1]
        curr_ma = obv_ma.iloc[-1]
        
        # Divergence Check on OBV? Harder.
        # Simple trend check
        if curr_obv > curr_ma:
            decision = "BUY"
        else:
            decision = "SELL"
            
        return decision, (curr_obv, curr_ma), 0

    def get_cci_decision(self):
        """
        Returns decision based on CCI.
        CCI > 100 -> BUY (Momentum)
        CCI < -100 -> SELL (Momentum)
        Else -> HOLD
        """
        cci = self._calculate_cci()
        curr_cci = cci.iloc[-1]
        div = self._check_divergence(cci)
        
        if curr_cci > 100:
            decision = "BUY"
        elif curr_cci < -100:
            decision = "SELL"
        else:
            decision = "HOLD"
            
        return decision, (curr_cci, 0), div

    def calculate_final_score(self, df_decisions):
        """
        Aggregates all indicator decisions into a final score (0-100).
        """
        score = 0
        total_weight = 0
        
        # Scoring Map
        score_map = {
            "STRONG BUY": 2,
            "BUY": 1,
            "HOLD": 0,
            "NEUTRAL": 0,
            "WAIT": 0,
            "SELL": -1,
            "STRONG SELL": -2
        }
        
        # Categories and Weights
        # Trend (40%): MA, DEMA, KAMA, SUPERTREND, ICHIMOKU, SAR, ALLIGATOR, AROON, VWAP
        # Momentum (30%): RSI, STOCH, WILLIAMS_R, FISHER, WAVETREND, AWESOME, MACD, STOCHRSI, DMI, CCI
        # Volume (20%): MFI, CMF, DEMAND_INDEX, OBV
        # Other (10%): BB, MEDIAN, GATOR
        
        categories = {
            "TREND": ["MA", "DEMA", "KAMA", "SUPERTREND", "ICHIMOKU", "SAR", "ALLIGATOR", "AROON", "VWAP"],
            "MOMENTUM": ["RSI", "STOCH", "WILLIAMS_R", "FISHER", "WAVETREND", "AWESOME", "MACD", "STOCHRSI", "DMI", "CCI"],
            "VOLUME": ["MFI", "CMF", "DEMAND_INDEX", "OBV"],
            "OTHER": ["BB", "MEDIAN", "GATOR"]
        }
        
        cat_weights = {
            "TREND": 0.40,
            "MOMENTUM": 0.30,
            "VOLUME": 0.20,
            "OTHER": 0.10
        }
        
        # Category Scores
        cat_scores = {k: 0 for k in categories}
        cat_counts = {k: 0 for k in categories}
        
        for index, row in df_decisions.iterrows():
            indicator = row['Indicator']
            decision = row['Decision']
            divergence = row['Divergence']
            
            # Base Score
            # Use 'get' to handle unknown decisions gracefully
            val = score_map.get(decision, 0)
            
            # Divergence Impact (Very High Priority)
            if divergence == 1: # Bullish Div
                val += 2 
            elif divergence == -1: # Bearish Div
                val -= 2
                
            # Assign to Category
            found = False
            for cat, indicators in categories.items():
                if indicator in indicators:
                    cat_scores[cat] += val
                    cat_counts[cat] += 1
                    found = True
                    break
            
            if not found: # Fallback to OTHER
                 cat_scores["OTHER"] += val
                 cat_counts["OTHER"] += 1
                 
        # Calculate Weighted Score
        # Normalize each category to -100 to +100 range first
        # Max score per item is approx +/- 4 (Strong Buy + Divergence), but typically +/- 2 without divergence.
        # Let's normalize assuming max theoretical per item is 2 (excluding div bonus for simplicity of scale, or include it).
        # Let's map average value:
        # Avg Score = Sum / Count. Range approx -2.5 to +2.5.
        
        final_normalized_score = 0
        
        details = {}
        
        for cat in categories:
            if cat_counts[cat] > 0:
                avg = cat_scores[cat] / cat_counts[cat]
                # Normalize -2 to +2 range to 0-100.
                # -2 -> 0, 0 -> 50, +2 -> 100.
                # Formula: (Avg + 2) / 4 * 100
                
                # Handling overflow from divergence (e.g. avg could be 3)
                if avg > 2: avg = 2
                if avg < -2: avg = -2
                
                norm_score = (avg + 2) / 4 * 100
                details[cat] = norm_score
                final_normalized_score += norm_score * cat_weights[cat]
            else:
                details[cat] = 50.0 # Neutral if no indicators in category
        
        return final_normalized_score, details

    def prepare_rl_features(self):
        """
        Calculates all technical indicators and generates a normalized feature matrix 
        for Reinforcement Learning.
        
        Returns:
            pd.DataFrame: A DataFrame containing ~48 normalized features for every timestep.
        """
        # Ensure we have enough data
        if len(self.data) < 200:
            return pd.DataFrame() # Not enough data
            
        df = self.data.copy()
        
        # --- 1. Price Components ---
        # Log Returns (Clipped)
        df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))
        df['Log_Return'] = df['Log_Return'].clip(-0.1, 0.1)
        
        # Shadows / Body (Normalized by Close)
        df['Shadow_Up'] = (df['High'] - df[['Open', 'Close']].max(axis=1)) / df['Close']
        df['Shadow_Down'] = (df[['Open', 'Close']].min(axis=1) - df['Low']) / df['Close']
        df['Body'] = (df['Close'] - df['Open']) / df['Close']
        
        # --- 2. Trend Indicators ---
        # Get config for this market/horizon
        market = getattr(self, 'market', 'bist100')  # Default to bist100
        config = get_config(market, self.horizon) if get_config else None
        
        # MA Distance (Short/Long depend on horizon)
        if self.horizon == 'short':
            s_win, l_win = 9, 21
        else:
            s_win, l_win = 50, 200
             
        ma_s = self._calculate_sma(s_win)
        ma_l = self._calculate_sma(l_win)
        df['Dist_MA_Short'] = (df['Close'] - ma_s) / df['Close']
        df['Dist_MA_Long'] = (df['Close'] - ma_l) / df['Close']
        
        # DEMA
        dema_s = self._calculate_dema(df['Close'], s_win) 
        df['Dist_DEMA'] = (df['Close'] - dema_s) / df['Close']
        
        # KAMA
        kama = self._calculate_kama()
        df['Dist_KAMA'] = (df['Close'] - kama) / df['Close']
        
        # SuperTrend (Vectorized calculation needed or rely on existing loop method)
        # Using existing loop method - might be slow but robust
        st, st_trend = self._calculate_supertrend()
        df['Dist_SuperTrend'] = (df['Close'] - st) / df['Close']
        df['SuperTrend_Dir'] = st_trend # 1 or -1
        
        # Ichimoku - use config if available
        if config:
            ich_cfg = config.get('ichimoku', {})
            tenkan_period = ich_cfg.get('tenkan', 9)
            kijun_period = ich_cfg.get('kijun', 26)
            senkou_b_period = ich_cfg.get('senkou_b', 52)
            shift = ich_cfg.get('shift', 26)
        else:
            tenkan_period, kijun_period, senkou_b_period, shift = 9, 26, 52, 26
            
        tenkan = (df['High'].rolling(window=tenkan_period).max() + df['Low'].rolling(window=tenkan_period).min()) / 2
        kijun = (df['High'].rolling(window=kijun_period).max() + df['Low'].rolling(window=kijun_period).min()) / 2
        span_a = ((tenkan + kijun) / 2).shift(shift)
        span_b = ((df['High'].rolling(window=senkou_b_period).max() + df['Low'].rolling(window=senkou_b_period).min()) / 2).shift(shift)
        
        df['Ichimoku_TK'] = (tenkan - kijun) / df['Close']
        df['Ichimoku_Cloud'] = (span_a - span_b) / df['Close']
        
        # SAR
        sar = self._calculate_parabolic_sar()
        df['Dist_SAR'] = (df['Close'] - sar) / df['Close']
        
        # Alligator
        # Smoothed MA logic repeated here or assume roughly accurate
        jaw = df['Close'].rolling(window=13).mean().shift(8) # Approx
        lips = df['Close'].rolling(window=5).mean().shift(3)
        df['Alligator_Spread'] = (jaw - lips) / df['Close']
        
        # Aroon
        aroon_up, aroon_down, aroon_osc = self._calculate_aroon()
        df['Aroon_Osc'] = aroon_osc / 100.0
        
        # Median
        median = self._calculate_median_indicator()
        df['Dist_Median'] = (df['Close'] - median) / df['Close']
        
        # --- 3. Momentum Oscillators ---
        # RSI - use config if available
        rsi_period = config['rsi']['period'] if config else 14
        rsi = self._calculate_rsi(window=rsi_period)
        df['RSI_Norm'] = (rsi - 50) / 50.0
        
        # Stochastic
        stoch_k, stoch_d = self._calculate_stochastic()
        df['Stoch_K_Norm'] = (stoch_k - 50) / 50.0
        
        # Williams %R
        wr = self._calculate_williams_r()
        df['Williams_Norm'] = (wr + 50) / 50.0
        
        # Fisher
        fisher, _ = self._calculate_fisher()
        df['Fisher_Norm'] = fisher.clip(-2, 2) / 2.0
        
        # MACD - use config if available
        if config:
            macd_cfg = config.get('macd', {})
            macd_fast = macd_cfg.get('fast', 12)
            macd_slow = macd_cfg.get('slow', 26)
            macd_signal = macd_cfg.get('signal', 9)
        else:
            macd_fast, macd_slow, macd_signal = 12, 26, 9
        macd, signal = self._calculate_macd(fast=macd_fast, slow=macd_slow, signal=macd_signal)
        df['MACD_Norm'] = (macd - signal) / df['Close']
        
        # DMI / ADX
        adx, p_di, m_di = self._calculate_dmi()
        df['ADX_Norm'] = adx / 100.0
        df['DMI_Dir'] = (p_di - m_di) / 100.0
        
        # CMF
        cmf = self._calculate_cmf()
        df['CMF'] = cmf.clip(-0.5, 0.5)
        
        # MFI
        mfi = self._calculate_mfi()
        df['MFI_Norm'] = (mfi - 50) / 50.0
        
        # WaveTrend
        wt1, wt2 = self._calculate_wavetrend()
        df['WaveTrend_Diff'] = (wt1 - wt2) / 100.0 # Approx scale
        
        # --- 4. Volume & Volatility ---
        # Rel Volume
        vol_ma = self._calculate_volume_ma()
        df['Rel_Volume'] = ((df['Volume'] - vol_ma) / vol_ma).clip(-1, 5)
        
        # ATR
        atr = self._calculate_atr()
        df['ATR_Pct'] = atr / df['Close']
        
        # BB Width - use config if available
        if config:
            bb_cfg = config.get('bollinger', {})
            bb_period = bb_cfg.get('period', 20)
            bb_std = bb_cfg.get('std', 2.0)
        else:
            bb_period, bb_std = 20, 2.0
        bb_upper, bb_mid, bb_lower = self._calculate_bollinger_bands(window=bb_period, num_std=bb_std)
        df['BB_Width'] = (bb_upper - bb_lower) / bb_mid
        
        # Demand Index
        # Simplified calc to avoid circular method calls or re-implement
        # For now use placeholder or reuse method if efficient
        # reuse method _calculate_demand_index()
        di = self._calculate_demand_index()
        df['Demand_Index_Norm'] = di / 100.0
        
        # --- 5. New Indicators (VWAP, OBV, CCI) ---
        # VWAP Distance
        vwap = self._calculate_vwap()
        df['Dist_VWAP'] = (df['Close'] - vwap) / df['Close']
        
        # CCI Normalized
        cci = self._calculate_cci()
        df['CCI_Norm'] = cci / 100.0
        
        # OBV (Z-Score of OBV to normalize)
        obv = self._calculate_obv()
        obv_mean = obv.rolling(window=20).mean()
        obv_std = obv.rolling(window=20).std().replace(0, 1) # Avoid div by zero
        df['OBV_Z'] = (obv - obv_mean) / obv_std
        
        # --- 6. Divergence Proxies (Rolling Correlation - Window 30) ---
        # Correlation between Price and Indicator.
        # Negative correlation implies Divergence.
        window_corr = 30
        df['RSI_Correl'] = df['Close'].rolling(window_corr).corr(rsi)
        df['MACD_Correl'] = df['Close'].rolling(window_corr).corr(macd)
        df['CCI_Correl'] = df['Close'].rolling(window_corr).corr(cci)
        df['OBV_Correl'] = df['Close'].rolling(window_corr).corr(obv)
        df['Stoch_Correl'] = df['Close'].rolling(window_corr).corr(stoch_k)
        df['Williams_Correl'] = df['Close'].rolling(window_corr).corr(wr)
        df['Fisher_Correl'] = df['Close'].rolling(window_corr).corr(fisher)
        df['CMF_Correl'] = df['Close'].rolling(window_corr).corr(cmf)
        df['MFI_Correl'] = df['Close'].rolling(window_corr).corr(mfi)
        df['Demand_Correl'] = df['Close'].rolling(window_corr).corr(di)
        
        # --- CLEANUP ---
        # 1. Replace Infinite values (caused by div by zero) with 0
        df.replace([np.inf, -np.inf], 0, inplace=True)
        
        # 2. Drop initial NaNs generated by rolling windows (Lookback ~ 200)
        df.dropna(inplace=True)
        
        # Select only Feature Columns
        feature_cols = [
            'Close', # Required for RL PnL calculation
            'Log_Return', 'Shadow_Up', 'Shadow_Down', 'Body',
            'Dist_MA_Short', 'Dist_MA_Long', 'Dist_DEMA', 'Dist_KAMA', 
            'Dist_SuperTrend', 'SuperTrend_Dir', 'Ichimoku_TK', 'Ichimoku_Cloud',
            'Dist_SAR', 'Alligator_Spread', 'Aroon_Osc', 'Dist_Median',
            'RSI_Norm', 'Stoch_K_Norm', 'Williams_Norm', 'Fisher_Norm', 
            'MACD_Norm', 'ADX_Norm', 'DMI_Dir', 'CMF', 'MFI_Norm', 'WaveTrend_Diff',
            'Rel_Volume', 'ATR_Pct', 'BB_Width', 'Demand_Index_Norm',
            'Dist_VWAP', 'CCI_Norm', 'OBV_Z',
            'RSI_Correl', 'MACD_Correl', 'CCI_Correl', 'OBV_Correl',
            'Stoch_Correl', 'Williams_Correl', 'Fisher_Correl', 
            'CMF_Correl', 'MFI_Correl', 'Demand_Correl'
        ]
        
        # Ensure all columns exist (some might be missing if method failed?)
        final_cols = [c for c in feature_cols if c in df.columns]
        
        return df[final_cols]
