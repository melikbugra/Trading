"""
Resistance Breakout + Stochastic RSI Strategy

Long Sinyali:
    Ön Koşul: Fiyat > EMA200 (yükseliş trendi)
    Ana Koşul: Fiyat son direnç seviyesinin üstüne çıkmış (breakout)
    Giriş Tetikleyicisi: Stochastic RSI 20 seviyesini alttan yukarı kesmiş

    Entry: Güncel fiyat (tüm koşullar sağlandığında)
    Stop Loss: Son dip - ATR buffer
    Take Profit: Risk × R:R oranına göre
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from .base import BaseStrategy, StrategyResult


class ResistanceBreakoutStrategy(BaseStrategy):
    """
    Resistance Breakout + Stochastic RSI Strategy.

    Yükseliş trendinde direnç kırılımı ile Stochastic RSI momentum teyidi alan
    bir breakout stratejisi. Sadece LONG pozisyonlar için tasarlandı.

    Parameters:
        ema_period: Trend EMA periyodu (default: 200)
        rsi_period: RSI periyodu (default: 14)
        stoch_period: Stochastic RSI lookback (default: 14)
        stoch_k: %K smooth periyodu (default: 3)
        stoch_d: %D smooth periyodu (default: 3)
        stoch_oversold: Aşırı satım seviyesi / giriş tetikleyici (default: 20)
        pivot_bars: Pivot tespiti için N-bar (default: 5)
        atr_period: ATR periyodu (default: 14)
        atr_multiplier: SL buffer çarpanı (default: 0.5)
    """

    name = "Direnç Kırılımı + Stochastic RSI"
    description = "EMA200 üstünde, direnç kırılımı sonrası StochRSI momentum teyidi"

    default_params = {
        "ema_period": 200,
        "rsi_period": 14,
        "stoch_period": 14,
        "stoch_k": 3,
        "stoch_d": 3,
        "stoch_oversold": 20,
        "pivot_bars": 5,
        "atr_period": 14,
        "atr_multiplier": 0.5,
    }

    def calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_stochastic_rsi(
        self,
        close: pd.Series,
        rsi_period: int = 14,
        stoch_period: int = 14,
        k_period: int = 3,
        d_period: int = 3,
    ) -> tuple:
        """
        Calculate Stochastic RSI.

        Stoch_RSI = (RSI - RSI_min) / (RSI_max - RSI_min) × 100
        %K = SMA(Stoch_RSI, k_period)
        %D = SMA(%K, d_period)

        Returns:
            (stoch_k, stoch_d) - %K and %D lines
        """
        rsi = self.calculate_rsi(close, rsi_period)

        # Calculate Stochastic of RSI
        rsi_min = rsi.rolling(window=stoch_period).min()
        rsi_max = rsi.rolling(window=stoch_period).max()

        # Avoid division by zero
        rsi_range = rsi_max - rsi_min
        rsi_range = rsi_range.replace(0, np.nan)

        stoch_rsi = ((rsi - rsi_min) / rsi_range) * 100

        # Smooth with SMA for %K and %D
        stoch_k = stoch_rsi.rolling(window=k_period).mean()
        stoch_d = stoch_k.rolling(window=d_period).mean()

        return stoch_k, stoch_d

    def evaluate(self, data: pd.DataFrame) -> StrategyResult:
        """
        Evaluate Resistance Breakout + Stochastic RSI strategy.

        Returns StrategyResult with:
            - precondition_met: Price > EMA200 (uptrend)
            - main_condition_met: Breakout + StochRSI momentum confirmation
        """
        result = StrategyResult()

        # Need enough data for EMA200 and indicators
        min_required = max(
            self.params["ema_period"],
            self.params["rsi_period"] + self.params["stoch_period"] + self.params["stoch_k"],
        )

        if data.empty or len(data) < min_required:
            result.notes = "Yetersiz veri"
            return result

        close = data["Close"]
        current_price = close.iloc[-1]
        result.current_price = current_price

        # 1. Calculate EMA200
        ema200 = self.calculate_ema(close, self.params["ema_period"])
        current_ema = ema200.iloc[-1]

        # 2. Calculate Stochastic RSI
        stoch_k, stoch_d = self.calculate_stochastic_rsi(
            close,
            self.params["rsi_period"],
            self.params["stoch_period"],
            self.params["stoch_k"],
            self.params["stoch_d"],
        )

        current_stoch_k = stoch_k.iloc[-1]
        prev_stoch_k = stoch_k.iloc[-2]
        oversold_level = self.params["stoch_oversold"]

        # 3. Find last resistance (pivot high) and support (pivot low)
        last_peak, last_trough = self.get_last_peak_trough(
            data, self.params["pivot_bars"]
        )
        result.last_peak = last_peak
        result.last_trough = last_trough

        # Store indicator values in extra_data
        result.extra_data = {
            "ema200": round(current_ema, 4),
            "stoch_k": round(current_stoch_k, 4) if not pd.isna(current_stoch_k) else None,
            "stoch_d": round(stoch_d.iloc[-1], 4) if not pd.isna(stoch_d.iloc[-1]) else None,
            "price_above_ema": current_price > current_ema,
            "resistance_level": round(last_peak, 4) if last_peak else None,
            "support_level": round(last_trough, 4) if last_trough else None,
        }

        # === LONG SIGNAL LOGIC ===
        # This strategy only generates LONG signals
        result.direction = "long"

        # Precondition: Price > EMA200 (uptrend)
        price_above_ema = current_price > current_ema

        if not price_above_ema:
            result.notes = "Fiyat EMA200 altında, yükseliş trendi yok"
            return result

        result.precondition_met = True

        # Check if we have valid peak/trough
        if last_peak is None or last_trough is None:
            result.notes = "Ön koşul sağlandı (EMA200 üstünde), tepe/dip bulunamadı"
            return result

        # Main Condition: Price broke above resistance (last peak)
        breakout_occurred = current_price > last_peak

        # Entry Trigger: Stochastic RSI crosses above oversold level (20)
        stoch_cross_up = (
            not pd.isna(prev_stoch_k)
            and not pd.isna(current_stoch_k)
            and prev_stoch_k < oversold_level
            and current_stoch_k >= oversold_level
        )

        result.extra_data["breakout_occurred"] = breakout_occurred
        result.extra_data["stoch_cross_up"] = stoch_cross_up

        if breakout_occurred and stoch_cross_up:
            result.main_condition_met = True
            result.notes = f"Direnç kırılımı ({last_peak:.2f}) + StochRSI momentum teyidi → LONG"

            # Calculate levels
            # Entry: Current price
            entry = current_price

            # Stop Loss: Last trough - ATR buffer
            atr = self.calculate_atr(data, self.params["atr_period"])
            current_atr = atr.iloc[-1]
            buffer = current_atr * self.params["atr_multiplier"]

            stop_loss = last_trough - buffer

            # Calculate risk and take profit
            risk = entry - stop_loss

            # Validate minimum risk (avoid too tight stops)
            min_atr_risk = 0.5
            max_atr_risk = 2.5

            if risk < current_atr * min_atr_risk:
                stop_loss = entry - (current_atr * min_atr_risk)
                risk = entry - stop_loss
            elif risk > current_atr * max_atr_risk:
                stop_loss = entry - (current_atr * max_atr_risk)
                risk = entry - stop_loss

            take_profit = entry + (risk * self.risk_reward_ratio)

            result.entry_price = round(entry, 4)
            result.stop_loss = round(stop_loss, 4)
            result.take_profit = round(take_profit, 4)

        elif breakout_occurred:
            result.notes = f"Direnç kırıldı ({last_peak:.2f}), StochRSI momentum teyidi bekleniyor"
        else:
            result.notes = f"Ön koşul sağlandı, direnç kırılımı bekleniyor (direnç: {last_peak:.2f})"

        return result

    def get_status_text(self, result: StrategyResult) -> str:
        """Get human-readable status text."""
        if result.main_condition_met:
            return f"🎯 LONG SİNYALİ! Entry: {result.entry_price}, SL: {result.stop_loss}, TP: {result.take_profit}"
        elif result.precondition_met:
            extra = result.extra_data
            if extra.get("breakout_occurred"):
                return f"⏳ Direnç kırıldı, StochRSI teyidi bekleniyor (K: {extra.get('stoch_k', 'N/A')})"
            return f"⏳ EMA200 üstünde, direnç kırılımı bekleniyor (direnç: {extra.get('resistance_level', 'N/A')})"
        else:
            return "❌ Ön koşul sağlanmadı (fiyat EMA200 altında)"
