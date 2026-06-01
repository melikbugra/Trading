"""
Base strategy class and common utilities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd
import numpy as np


def to_python_native(value):
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    elif isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    elif isinstance(value, np.bool_):
        return bool(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, dict):
        return {k: to_python_native(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [to_python_native(v) for v in value]
    return value


@dataclass
class StrategyResult:
    """Result of a strategy evaluation."""

    # Status
    precondition_met: bool = False  # Ön koşul sağlanıyor mu?
    main_condition_met: bool = False  # Ana koşul sağlandı mı?

    # Signal data (when main_condition_met is True)
    direction: str = "long"  # "long" or "short"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_tolerance: Optional[float] = None  # limit-entry band width (e.g. 0.5*ATR)

    # Peak/Trough
    last_peak: Optional[float] = None
    last_trough: Optional[float] = None

    # Current market data
    current_price: Optional[float] = None

    # Extra info
    notes: str = ""
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def get_json_safe_data(self) -> Dict[str, Any]:
        """Return all numeric fields as native Python types for JSON serialization."""
        return {
            "precondition_met": bool(self.precondition_met),
            "main_condition_met": bool(self.main_condition_met),
            "direction": self.direction,
            "entry_price": to_python_native(self.entry_price),
            "stop_loss": to_python_native(self.stop_loss),
            "take_profit": to_python_native(self.take_profit),
            "entry_tolerance": to_python_native(self.entry_tolerance),
            "last_peak": to_python_native(self.last_peak),
            "last_trough": to_python_native(self.last_trough),
            "current_price": to_python_native(self.current_price),
            "notes": self.notes,
            "extra_data": to_python_native(self.extra_data),
        }


class BaseStrategy(ABC):
    """
    Base class for all trading strategies.

    Every strategy must implement:
    - evaluate(data): Checks precondition and main condition
    - calculate_levels(data, direction): Calculates entry, SL, TP
    """

    # Strategy metadata
    name: str = "BaseStrategy"
    description: str = "Base strategy class"

    # Default parameters
    default_params: Dict[str, Any] = {}

    def __init__(self, params: Dict[str, Any] = None, risk_reward_ratio: float = 2.0):
        """
        Initialize strategy with parameters.

        Args:
            params: Strategy-specific parameters
            risk_reward_ratio: Risk/Reward ratio for TP calculation
        """
        self.params = {**self.default_params, **(params or {})}
        self.risk_reward_ratio = risk_reward_ratio
        # Long-only mode: BIST spot/cash market does not allow retail intraday
        # short selling, so SHORT signals are suppressed by default. Set
        # params["long_only"] = False to re-enable SHORT (e.g. for VIOP).
        self.long_only = bool(self.params.get("long_only", True))

    @abstractmethod
    def evaluate(self, data: pd.DataFrame) -> StrategyResult:
        """
        Evaluate the strategy on given data.

        Args:
            data: OHLCV DataFrame with columns: Open, High, Low, Close, Volume

        Returns:
            StrategyResult with precondition/main condition status and signal details
        """
        pass

    def find_peaks_troughs(self, data: pd.DataFrame, n_bars: int = 5) -> tuple:
        """
        Find peaks and troughs using N-bar pivot method.

        A peak is a bar where high is higher than N bars before and after.
        A trough is a bar where low is lower than N bars before and after.

        Args:
            data: OHLCV DataFrame
            n_bars: Number of bars to look before/after

        Returns:
            (peaks_series, troughs_series) - Series with NaN except at pivot points
        """
        high = data["High"]
        low = data["Low"]

        peaks = pd.Series(np.nan, index=data.index)
        troughs = pd.Series(np.nan, index=data.index)

        for i in range(n_bars, len(data) - n_bars):
            # Check for peak
            window_high = high.iloc[i - n_bars : i + n_bars + 1]
            if high.iloc[i] == window_high.max():
                peaks.iloc[i] = high.iloc[i]

            # Check for trough
            window_low = low.iloc[i - n_bars : i + n_bars + 1]
            if low.iloc[i] == window_low.min():
                troughs.iloc[i] = low.iloc[i]

        return peaks, troughs

    def get_last_peak_trough(self, data: pd.DataFrame, n_bars: int = 5) -> tuple:
        """
        Get the most recent confirmed peak and trough.

        Returns:
            (last_peak_price, last_trough_price)
        """
        peaks, troughs = self.find_peaks_troughs(data, n_bars)

        # Get last non-NaN values
        last_peak = peaks.dropna().iloc[-1] if not peaks.dropna().empty else None
        last_trough = troughs.dropna().iloc[-1] if not troughs.dropna().empty else None

        return last_peak, last_trough

    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high = data["High"]
        low = data["Low"]
        close = data["Close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        return tr.rolling(window=period).mean()

    def calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    def calculate_macd(
        self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple:
        """Calculate MACD and Signal line."""
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    def annotate_trade_plan(
        self, data: pd.DataFrame, result: "StrategyResult"
    ) -> "StrategyResult":
        """
        Enrich a main-condition result with the limit-entry tolerance band,
        an R-multiple partial take-profit (TP1) and a trailing-stop config.

        All values are R-based: R = |entry - stop_loss|.
        - entry_tolerance: limit-order band width = entry_tol_atr * ATR
        - extra_data["entry_zone"]: {low, high} fillable limit zone
        - extra_data["partial_tp"]: {price, pct, r}  (e.g. sell 50% at +1R)
        - extra_data["trailing"]: {enabled, atr_mult, atr, activate_after}

        Tunable via strategy params: entry_tol_atr, partial_tp_enabled, tp1_r,
        tp1_pct, trailing_enabled, trail_atr_mult.
        """
        if (
            not result.main_condition_met
            or result.entry_price is None
            or result.stop_loss is None
        ):
            return result

        atr = self.calculate_atr(data)
        current_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0

        entry = float(result.entry_price)
        sl = float(result.stop_loss)
        direction = result.direction
        risk = abs(entry - sl)

        extra = dict(result.extra_data or {})

        # Limit-entry tolerance band
        tol = current_atr * float(self.params.get("entry_tol_atr", 0.5))
        result.entry_tolerance = round(tol, 4)
        if direction == "long":
            extra["entry_zone"] = {"low": round(entry, 4), "high": round(entry + tol, 4)}
        else:
            extra["entry_zone"] = {"low": round(entry - tol, 4), "high": round(entry, 4)}

        # R-based partial take-profit (TP1)
        if self.params.get("partial_tp_enabled", True) and risk > 0:
            tp1_r = float(self.params.get("tp1_r", 1.0))
            tp1_pct = float(self.params.get("tp1_pct", 0.5))
            if direction == "long":
                tp1 = entry + risk * tp1_r
            else:
                tp1 = entry - risk * tp1_r
            extra["partial_tp"] = {"price": round(tp1, 4), "pct": tp1_pct, "r": tp1_r}

        # Trailing-stop config (move to breakeven after TP1, then trail by ATR)
        if self.params.get("trailing_enabled", True):
            extra["trailing"] = {
                "enabled": True,
                "atr_mult": float(self.params.get("trail_atr_mult", 2.0)),
                "atr": round(current_atr, 4),
                "activate_after": "tp1",
            }

        result.extra_data = extra
        return result

    def calculate_levels(
        self,
        data: pd.DataFrame,
        direction: str,
        last_peak: float,
        last_trough: float,
        atr_multiplier: float = 0.25,  # Reduced from 0.5 for tighter levels
        max_atr_risk: float = 2.5,  # Maximum risk in ATR units
        min_atr_risk: float = 0.5,  # Minimum risk in ATR units
    ) -> tuple:
        """
        Calculate entry, stop loss, and take profit levels.

        For LONG:
            - Entry: last_peak + buffer
            - Stop Loss: MAX(last_trough - buffer, entry - max_atr_risk * ATR)
            - Take Profit: Entry + (Entry - SL) * risk_reward_ratio

        For SHORT:
            - Entry: last_trough - buffer
            - Stop Loss: MIN(last_peak + buffer, entry + max_atr_risk * ATR)
            - Take Profit: Entry - (SL - Entry) * risk_reward_ratio

        Args:
            data: OHLCV DataFrame
            direction: "long" or "short"
            last_peak: Last confirmed peak price
            last_trough: Last confirmed trough price
            atr_multiplier: Buffer = ATR * multiplier (default 0.25)
            max_atr_risk: Maximum stop distance in ATR units (default 2.5)
            min_atr_risk: Minimum stop distance in ATR units (default 0.5)

        Returns:
            (entry_price, stop_loss, take_profit) or (None, None, None) if invalid
        """
        atr = self.calculate_atr(data)
        current_atr = atr.iloc[-1]
        buffer = current_atr * atr_multiplier
        max_stop_distance = current_atr * max_atr_risk
        min_stop_distance = current_atr * min_atr_risk

        if direction == "long":
            entry = last_peak + buffer

            # Calculate stop loss with cap
            natural_stop = last_trough - buffer
            capped_stop = entry - max_stop_distance
            stop_loss = max(natural_stop, capped_stop)  # Use tighter stop

            # Validate minimum risk
            risk = entry - stop_loss
            if risk < min_stop_distance:
                # Stop is too close, signal may be invalid (noise)
                # Expand to minimum distance
                stop_loss = entry - min_stop_distance
                risk = min_stop_distance

            take_profit = entry + (risk * self.risk_reward_ratio)

        else:  # short
            entry = last_trough - buffer

            # Calculate stop loss with cap
            natural_stop = last_peak + buffer
            capped_stop = entry + max_stop_distance
            stop_loss = min(natural_stop, capped_stop)  # Use tighter stop

            # Validate minimum risk
            risk = stop_loss - entry
            if risk < min_stop_distance:
                # Stop is too close, signal may be invalid (noise)
                # Expand to minimum distance
                stop_loss = entry + min_stop_distance
                risk = min_stop_distance

            take_profit = entry - (risk * self.risk_reward_ratio)

        return round(entry, 4), round(stop_loss, 4), round(take_profit, 4)
