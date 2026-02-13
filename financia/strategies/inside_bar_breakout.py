"""
Inside Bar Breakout Strategy (Saatlik Mum - Gün İçi)

Inside Bar: Bir mumun High ve Low değeri, bir önceki mumun (Mother Bar)
High ve Low değerleri arasında kalan mumdur. Bu, piyasanın sıkıştığını ve
yakında güçlü bir hareket olabileceğini gösterir.

Long Sinyali:
    Ön Koşul: Inside Bar pattern tespit edildi (sıkışma var)
    Ana Koşul: Fiyat Mother Bar'ın High'ını yukarı kırdığında

    Entry: Mother Bar High + buffer
    Stop Loss: Mother Bar Low - buffer (veya Inside Bar Low - buffer)
    Take Profit: Risk/Reward oranına göre

Short Sinyali:
    Ön Koşul: Inside Bar pattern tespit edildi (sıkışma var)
    Ana Koşul: Fiyat Mother Bar'ın Low'unu aşağı kırdığında

    Entry: Mother Bar Low - buffer
    Stop Loss: Mother Bar High + buffer (veya Inside Bar High + buffer)
    Take Profit: Risk/Reward oranına göre

Filtreler:
    - EMA trend filtresi: Trend yönünde işlem al (opsiyonel)
    - Birden fazla Inside Bar (sıkışma derinliği) → daha güçlü sinyal
    - ATR bazlı buffer ve risk yönetimi
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from .base import BaseStrategy, StrategyResult


class InsideBarBreakoutStrategy(BaseStrategy):
    """
    Inside Bar Breakout Strategy for intraday (1h candles).

    Detects inside bar patterns (consolidation) and trades the breakout
    direction. Uses EMA as optional trend filter.

    Parameters:
        ema_period: EMA period for trend filter (default: 50, 0 to disable)
        atr_period: ATR period for buffer calculation (default: 14)
        atr_multiplier: Buffer = ATR * multiplier (default: 0.25)
        use_mother_bar_sl: If True, SL at Mother Bar extreme; if False, at Inside Bar extreme (default: True)
        min_mother_bar_atr: Minimum Mother Bar size in ATR units (default: 0.5)
        max_mother_bar_atr: Maximum Mother Bar size in ATR units (default: 3.0)
        lookback_bars: How many bars back to look for inside bar pattern (default: 5)
    """

    name = "Inside Bar Breakout"
    description = "Inside Bar sıkışma paterni tespit edildiğinde kırılım yönünde işlem. Gün içi 1 saatlik mumlar için optimize."

    default_params = {
        "ema_period": 50,  # 0 = trend filtresi kapalı
        "atr_period": 14,
        "atr_multiplier": 0.25,
        "use_mother_bar_sl": True,
        "min_mother_bar_atr": 0.5,
        "max_mother_bar_atr": 3.0,
        "lookback_bars": 5,
    }

    def _find_inside_bars(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Find inside bar patterns in the data.

        An inside bar has its High <= previous bar's High
        AND its Low >= previous bar's Low.

        Returns DataFrame with columns:
            - is_inside_bar: bool
            - mother_bar_high: float (the bar before inside bar)
            - mother_bar_low: float
            - inside_bar_high: float
            - inside_bar_low: float
            - consecutive_inside_bars: int (how many consecutive IBs)
        """
        high = data["High"]
        low = data["Low"]

        is_inside = (high <= high.shift(1)) & (low >= low.shift(1))

        # Find mother bar values
        mother_high = high.shift(1)
        mother_low = low.shift(1)

        # Count consecutive inside bars
        consecutive = pd.Series(0, index=data.index)
        count = 0
        for i in range(len(is_inside)):
            if is_inside.iloc[i]:
                count += 1
                consecutive.iloc[i] = count
            else:
                count = 0

        result = pd.DataFrame(
            {
                "is_inside_bar": is_inside,
                "mother_bar_high": mother_high,
                "mother_bar_low": mother_low,
                "inside_bar_high": high,
                "inside_bar_low": low,
                "consecutive_inside_bars": consecutive,
            },
            index=data.index,
        )

        return result

    def evaluate(self, data: pd.DataFrame) -> StrategyResult:
        """
        Evaluate Inside Bar Breakout strategy.

        Logic:
        1. Scan recent bars for inside bar pattern
        2. If found, set precondition_met = True
        3. If current price breaks Mother Bar High/Low → main_condition_met = True
        4. Direction decided by breakout side (optionally filtered by EMA trend)
        """
        result = StrategyResult()

        min_bars = max(self.params["ema_period"], self.params["atr_period"], 20)
        if data.empty or len(data) < min_bars:
            result.notes = "Yetersiz veri"
            return result

        close = data["Close"]
        high = data["High"]
        low = data["Low"]
        current_price = close.iloc[-1]
        current_high = high.iloc[-1]
        current_low = low.iloc[-1]
        result.current_price = current_price

        # Calculate ATR
        atr = self.calculate_atr(data, self.params["atr_period"])
        current_atr = atr.iloc[-1]
        buffer = current_atr * self.params["atr_multiplier"]

        # Calculate EMA for trend filter (if enabled)
        ema_period = self.params["ema_period"]
        trend_direction = None  # None = no filter
        current_ema = None
        if ema_period > 0 and len(data) >= ema_period:
            ema = self.calculate_ema(close, ema_period)
            current_ema = ema.iloc[-1]
            trend_direction = "long" if current_price > current_ema else "short"

        # Find inside bars
        ib_data = self._find_inside_bars(data)

        # Look for inside bar pattern in recent bars (excluding current bar)
        lookback = self.params["lookback_bars"]
        recent_ibs = ib_data.iloc[-(lookback + 1) : -1]  # Exclude current bar

        # Find the most recent inside bar
        recent_inside = recent_ibs[recent_ibs["is_inside_bar"]]

        if recent_inside.empty:
            result.notes = "Inside Bar paterni yok"
            return result

        # Get the most recent inside bar pattern
        last_ib = recent_inside.iloc[-1]
        mother_high = last_ib["mother_bar_high"]
        mother_low = last_ib["mother_bar_low"]
        ib_high = last_ib["inside_bar_high"]
        ib_low = last_ib["inside_bar_low"]
        consecutive = int(last_ib["consecutive_inside_bars"])

        # Validate Mother Bar size
        mother_bar_size = mother_high - mother_low
        min_size = current_atr * self.params["min_mother_bar_atr"]
        max_size = current_atr * self.params["max_mother_bar_atr"]

        if mother_bar_size < min_size:
            result.notes = "Mother Bar çok küçük (düşük volatilite)"
            return result
        if mother_bar_size > max_size:
            result.notes = "Mother Bar çok büyük (aşırı volatilite)"
            return result

        # Store pattern info
        result.extra_data = {
            "mother_bar_high": round(float(mother_high), 4),
            "mother_bar_low": round(float(mother_low), 4),
            "inside_bar_high": round(float(ib_high), 4),
            "inside_bar_low": round(float(ib_low), 4),
            "consecutive_inside_bars": consecutive,
            "mother_bar_size_atr": round(float(mother_bar_size / current_atr), 2),
            "atr": round(float(current_atr), 4),
        }
        if current_ema is not None:
            result.extra_data["ema"] = round(float(current_ema), 4)
            result.extra_data["trend"] = trend_direction

        # Set peak/trough from mother bar levels
        result.last_peak = float(mother_high)
        result.last_trough = float(mother_low)

        # ---- PRECONDITION: Inside Bar pattern exists ----
        result.precondition_met = True

        # ---- MAIN CONDITION: Breakout detected ----
        # Check if current candle breaks Mother Bar levels
        broke_high = current_high > mother_high
        broke_low = current_low < mother_low

        # Both sides broken (whipsaw) → skip
        if broke_high and broke_low:
            result.notes = f"Inside Bar tespit edildi ({consecutive}x) ama iki yön de kırıldı - sinyal yok"
            return result

        use_mother_sl = self.params["use_mother_bar_sl"]

        # === LONG BREAKOUT ===
        if broke_high:
            # If trend filter is on and trend is short, skip
            if trend_direction == "short":
                result.direction = "long"
                result.notes = f"Inside Bar ({consecutive}x) yukarı kırılım var ama EMA{ema_period} altında - trend filtresi"
                return result

            result.direction = "long"
            result.main_condition_met = True

            entry = float(mother_high) + buffer
            sl_level = float(mother_low if use_mother_sl else ib_low) - buffer
            risk = entry - sl_level

            # Ensure minimum risk
            min_risk = current_atr * 0.5
            if risk < min_risk:
                sl_level = entry - min_risk
                risk = min_risk

            tp = entry + (risk * self.risk_reward_ratio)

            result.entry_price = round(entry, 4)
            result.stop_loss = round(sl_level, 4)
            result.take_profit = round(tp, 4)
            result.notes = f"Inside Bar ({consecutive}x) yukarı kırılım → LONG"

        # === SHORT BREAKOUT ===
        elif broke_low:
            # If trend filter is on and trend is long, skip
            if trend_direction == "long":
                result.direction = "short"
                result.notes = f"Inside Bar ({consecutive}x) aşağı kırılım var ama EMA{ema_period} üstünde - trend filtresi"
                return result

            result.direction = "short"
            result.main_condition_met = True

            entry = float(mother_low) - buffer
            sl_level = float(mother_high if use_mother_sl else ib_high) + buffer
            risk = sl_level - entry

            # Ensure minimum risk
            min_risk = current_atr * 0.5
            if risk < min_risk:
                sl_level = entry + min_risk
                risk = min_risk

            tp = entry - (risk * self.risk_reward_ratio)

            result.entry_price = round(entry, 4)
            result.stop_loss = round(sl_level, 4)
            result.take_profit = round(tp, 4)
            result.notes = f"Inside Bar ({consecutive}x) aşağı kırılım → SHORT"

        else:
            # No breakout yet - just waiting
            result.notes = (
                f"Inside Bar tespit edildi ({consecutive}x sıkışma), kırılım bekleniyor"
            )

        return result

    def get_status_text(self, result: StrategyResult) -> str:
        """Get human-readable status text."""
        if result.main_condition_met:
            direction_tr = "LONG" if result.direction == "long" else "SHORT"
            return (
                f"🎯 {direction_tr} SİNYALİ! "
                f"Entry: {result.entry_price}, SL: {result.stop_loss}, TP: {result.take_profit}"
            )
        elif result.precondition_met:
            cons = result.extra_data.get("consecutive_inside_bars", 1)
            return f"⏳ Inside Bar ({cons}x) sıkışma tespit edildi, kırılım bekleniyor"
        else:
            return "❌ Inside Bar paterni yok"
