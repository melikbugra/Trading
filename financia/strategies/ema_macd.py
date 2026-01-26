"""
EMA200 + MACD Strategy

Long Sinyali:
    Ön Koşul: Fiyat > EMA200
    Ana Koşul: MACD çizgisi signal çizgisini yukarı kestiğinde (ön koşul hala geçerliyken)

    Entry: Son tepe + buffer (ATR bazlı)
    Stop Loss: Son dip - buffer
    Take Profit: Risk/Reward oranına göre

Short Sinyali:
    Ön Koşul: Fiyat < EMA200
    Ana Koşul: MACD çizgisi signal çizgisini aşağı kestiğinde (ön koşul hala geçerliyken)

    Entry: Son dip - buffer
    Stop Loss: Son tepe + buffer
    Take Profit: Risk/Reward oranına göre
"""

import pandas as pd
from typing import Dict, Any

from .base import BaseStrategy, StrategyResult


class EMAMACDStrategy(BaseStrategy):
    """
    EMA200 + MACD Crossover Strategy.

    Parameters:
        ema_period: EMA period (default: 200)
        macd_fast: MACD fast period (default: 12)
        macd_slow: MACD slow period (default: 26)
        macd_signal: MACD signal period (default: 9)
        pivot_bars: N-bar pivot for peak/trough detection (default: 5)
        atr_period: ATR period for buffer calculation (default: 14)
        atr_multiplier: Buffer = ATR * multiplier (default: 0.5)
    """

    name = "EMA200 + MACD"
    description = "Fiyat EMA200 üzerindeyken MACD yukarı keserse LONG, EMA200 altındayken MACD aşağı keserse SHORT sinyali"

    default_params = {
        "ema_period": 200,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "pivot_bars": 5,
        "atr_period": 14,
        "atr_multiplier": 0.5,
    }

    def evaluate(self, data: pd.DataFrame) -> StrategyResult:
        """
        Evaluate EMA200 + MACD strategy.

        Returns StrategyResult with:
            - precondition_met: Price > EMA200 (long) or Price < EMA200 (short)
            - main_condition_met: MACD crossover occurred while precondition met
        """
        result = StrategyResult()

        if data.empty or len(data) < self.params["ema_period"]:
            result.notes = "Insufficient data"
            return result

        close = data["Close"]
        current_price = close.iloc[-1]
        result.current_price = current_price

        # Calculate indicators
        ema200 = self.calculate_ema(close, self.params["ema_period"])
        current_ema = ema200.iloc[-1]

        macd, signal = self.calculate_macd(
            close,
            self.params["macd_fast"],
            self.params["macd_slow"],
            self.params["macd_signal"],
        )

        current_macd = macd.iloc[-1]
        current_signal = signal.iloc[-1]
        prev_macd = macd.iloc[-2]
        prev_signal = signal.iloc[-2]

        # Get peak/trough for level calculations
        last_peak, last_trough = self.get_last_peak_trough(
            data, self.params["pivot_bars"]
        )
        result.last_peak = last_peak
        result.last_trough = last_trough

        # Store indicator values in extra_data
        result.extra_data = {
            "ema200": round(current_ema, 4),
            "macd": round(current_macd, 4),
            "macd_signal": round(current_signal, 4),
            "price_above_ema": current_price > current_ema,
        }

        # Check preconditions
        price_above_ema = current_price > current_ema
        price_below_ema = current_price < current_ema

        # Check MACD crossovers
        bullish_cross = prev_macd < prev_signal and current_macd > current_signal
        bearish_cross = prev_macd > prev_signal and current_macd < current_signal

        # === LONG SIGNAL ===
        if price_above_ema:
            result.precondition_met = True
            result.direction = "long"

            if bullish_cross:
                result.main_condition_met = True
                result.notes = "Fiyat EMA200 üzerinde, MACD yukarı kesti → LONG"

                # Calculate levels
                if last_peak is not None and last_trough is not None:
                    entry, sl, tp = self.calculate_levels(
                        data,
                        "long",
                        last_peak,
                        last_trough,
                        self.params["atr_multiplier"],
                    )
                    result.entry_price = entry
                    result.stop_loss = sl
                    result.take_profit = tp
                else:
                    result.notes += " (Tepe/Dip bulunamadı)"

        # === SHORT SIGNAL ===
        elif price_below_ema:
            result.precondition_met = True
            result.direction = "short"

            if bearish_cross:
                result.main_condition_met = True
                result.notes = "Fiyat EMA200 altında, MACD aşağı kesti → SHORT"

                # Calculate levels
                if last_peak is not None and last_trough is not None:
                    entry, sl, tp = self.calculate_levels(
                        data,
                        "short",
                        last_peak,
                        last_trough,
                        self.params["atr_multiplier"],
                    )
                    result.entry_price = entry
                    result.stop_loss = sl
                    result.take_profit = tp
                else:
                    result.notes += " (Tepe/Dip bulunamadı)"

        return result

    def get_status_text(self, result: StrategyResult) -> str:
        """Get human-readable status text."""
        if result.main_condition_met:
            direction_tr = "LONG" if result.direction == "long" else "SHORT"
            return f"🎯 {direction_tr} SİNYALİ! Entry: {result.entry_price}, SL: {result.stop_loss}, TP: {result.take_profit}"
        elif result.precondition_met:
            direction_tr = "yukarı" if result.direction == "long" else "aşağı"
            return f"⏳ Ön koşul sağlandı (EMA200 {direction_tr}), MACD kesişimi bekleniyor"
        else:
            return "❌ Ön koşul sağlanmadı"
