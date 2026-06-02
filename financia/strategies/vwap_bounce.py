"""
VWAP Bounce Strategy (Gün İçi)

VWAP (Volume Weighted Average Price): Hacim ağırlıklı ortalama fiyat.
Kurumsal yatırımcıların temel referans noktası. Her gün sıfırdan hesaplanır.

VWAP = Σ(Typical Price × Volume) / Σ(Volume)
Typical Price = (High + Low + Close) / 3

Bantlar: VWAP ± StdDev (Bollinger benzeri)

Long Sinyali:
    Ön Koşul: Fiyat VWAP civarında (±1σ bant içinde), trend yukarı
    Ana Koşul: Fiyat VWAP'a dokunup sıçradı + hacim onayı

    Entry: Bounce anındaki fiyat + buffer
    Stop Loss: VWAP - 1σ
    Take Profit: Risk/Reward oranına göre

Short Sinyali:
    Ön Koşul: Fiyat VWAP civarında (±1σ bant içinde), trend aşağı
    Ana Koşul: Fiyat VWAP'a dokunup reddedildi + hacim onayı

    Entry: Bounce anındaki fiyat - buffer
    Stop Loss: VWAP + 1σ
    Take Profit: Risk/Reward oranına göre

Filtreler:
    - Hacim onayı: Bounce mumunun hacmi > ortalama hacim
    - Trend filtresi: Fiyat VWAP üzerindeyse sadece LONG, altındaysa sadece SHORT
    - İlk saati atla: VWAP stabilize olması için (opsiyonel)
    - ATR bazlı buffer ve risk yönetimi
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from .base import BaseStrategy, StrategyResult


class VWAPBounceStrategy(BaseStrategy):
    """
    VWAP Bounce Strategy for intraday trading (1h candles).

    Detects bounces off VWAP level with volume confirmation.
    Uses VWAP standard deviation bands for SL/TP.

    Parameters:
        vwap_touch_threshold: How close to VWAP counts as "touch" in % (default: 0.3)
        volume_multiplier: Volume must be > avg * this to confirm (default: 1.0)
        volume_lookback: Bars to average volume over (default: 20)
        atr_period: ATR period for buffer (default: 14)
        atr_buffer_mult: Buffer = ATR * this (default: 0.1)
        band_std_mult: Std dev multiplier for VWAP bands (default: 1.0)
        min_bars_from_open: Skip first N bars of the day (default: 1)
        trend_filter: Use VWAP as trend filter (default: True)
    """

    name = "VWAP Bounce"
    description = "VWAP seviyesinden sıçrama tespiti. Gün içi 1 saatlik mumlar, hacim onaylı."
    # VWAP bounce is an intraday trend-continuation entry (buy the pullback to VWAP
    # in an uptrend), so it pairs best with the daily-TREND universe.
    category = "trend"

    default_params = {
        "vwap_touch_threshold": 0.3,  # %0.3 yakınlık = dokunuş
        "volume_multiplier": 1.0,  # Hacim >= ortalama × 1.0
        "volume_lookback": 20,  # Hacim ortalaması için son 20 bar
        "atr_period": 14,
        "atr_buffer_mult": 0.1,  # Entry buffer
        "band_std_mult": 1.0,  # VWAP ± 1σ
        "min_bars_from_open": 1,  # İlk 1 bari atla
        "trend_filter": True,  # VWAP'a göre trend filtresi
        "long_only": True,  # BIST spot: sadece LONG sinyali üret
        # Limit-giriş + kademeli kâr + trailing (R-bazlı)
        "entry_tol_atr": 0.5,
        "partial_tp_enabled": True,
        "tp1_r": 1.0,
        "tp1_pct": 0.5,
        "trailing_enabled": True,
        "trail_atr_mult": 2.0,
    }

    def _calculate_vwap(self, data: pd.DataFrame) -> tuple:
        """
        Calculate VWAP and standard deviation bands for intraday data.

        VWAP resets daily. For each trading day, cumulative VWAP is computed.

        Returns:
            (vwap_series, upper_band, lower_band)
        """
        typical_price = (data["High"] + data["Low"] + data["Close"]) / 3
        volume = data["Volume"]

        # Group by trading day for daily reset
        # Use date part of the index
        if hasattr(data.index, 'date'):
            dates = pd.Series(data.index.date, index=data.index)
        else:
            dates = pd.Series(0, index=data.index)  # fallback: treat all as one day

        vwap = pd.Series(np.nan, index=data.index)
        upper_band = pd.Series(np.nan, index=data.index)
        lower_band = pd.Series(np.nan, index=data.index)

        std_mult = self.params["band_std_mult"]

        for day, group_idx in dates.groupby(dates).groups.items():
            day_mask = data.index.isin(group_idx)
            day_tp = typical_price[day_mask]
            day_vol = volume[day_mask]

            # Cumulative VWAP
            cum_tp_vol = (day_tp * day_vol).cumsum()
            cum_vol = day_vol.cumsum()

            # Avoid division by zero
            day_vwap = cum_tp_vol / cum_vol.replace(0, np.nan)

            # Cumulative standard deviation
            # Variance = Σ(vol * (tp - vwap)²) / Σ(vol)
            day_vwap_vals = day_vwap.values
            day_tp_vals = day_tp.values
            day_vol_vals = day_vol.values

            day_upper = pd.Series(np.nan, index=day_tp.index)
            day_lower = pd.Series(np.nan, index=day_tp.index)

            for i in range(len(day_tp_vals)):
                if i == 0:
                    day_upper.iloc[i] = day_vwap_vals[i]
                    day_lower.iloc[i] = day_vwap_vals[i]
                    continue

                # Running sum of squared deviations weighted by volume
                tp_slice = day_tp_vals[: i + 1]
                vol_slice = day_vol_vals[: i + 1]
                vwap_val = day_vwap_vals[i]

                if np.isnan(vwap_val) or np.sum(vol_slice) == 0:
                    continue

                variance = np.sum(vol_slice * (tp_slice - vwap_val) ** 2) / np.sum(
                    vol_slice
                )
                std = np.sqrt(variance)

                day_upper.iloc[i] = vwap_val + std * std_mult
                day_lower.iloc[i] = vwap_val - std * std_mult

            vwap[day_mask] = day_vwap
            upper_band[day_mask] = day_upper
            lower_band[day_mask] = day_lower

        return vwap, upper_band, lower_band

    def _get_bar_index_in_day(self, data: pd.DataFrame) -> pd.Series:
        """Get how many bars from the start of each day (for skipping first bars)."""
        if hasattr(data.index, 'date'):
            dates = pd.Series(data.index.date, index=data.index)
        else:
            return pd.Series(range(len(data)), index=data.index)

        bar_idx = pd.Series(0, index=data.index)
        for day, group_idx in dates.groupby(dates).groups.items():
            day_mask = data.index.isin(group_idx)
            count = day_mask.sum()
            bar_idx[day_mask] = range(count)

        return bar_idx

    def evaluate(self, data: pd.DataFrame) -> StrategyResult:
        """
        Evaluate VWAP Bounce strategy.

        Logic:
        1. Calculate VWAP and bands for the day
        2. Check if price is near VWAP (precondition)
        3. Check for bounce with volume confirmation (main condition)
        4. Direction decided by price position relative to VWAP
        """
        result = StrategyResult()

        min_bars = max(self.params["atr_period"], self.params["volume_lookback"], 20)
        if data.empty or len(data) < min_bars:
            result.notes = "Yetersiz veri"
            return result

        # Check if volume data exists
        if "Volume" not in data.columns or data["Volume"].sum() == 0:
            result.notes = "Hacim verisi yok"
            return result

        close = data["Close"]
        high = data["High"]
        low = data["Low"]
        volume = data["Volume"]
        current_price = float(close.iloc[-1])
        current_high = float(high.iloc[-1])
        current_low = float(low.iloc[-1])
        current_volume = float(volume.iloc[-1])
        result.current_price = current_price

        # Calculate ATR
        atr = self.calculate_atr(data, self.params["atr_period"])
        current_atr = float(atr.iloc[-1])
        buffer = current_atr * self.params["atr_buffer_mult"]

        # Calculate VWAP and bands
        vwap, upper_band, lower_band = self._calculate_vwap(data)
        current_vwap = vwap.iloc[-1]

        if np.isnan(current_vwap):
            result.notes = "VWAP hesaplanamadı"
            return result

        current_vwap = float(current_vwap)
        current_upper = float(upper_band.iloc[-1]) if not np.isnan(upper_band.iloc[-1]) else current_vwap + current_atr
        current_lower = float(lower_band.iloc[-1]) if not np.isnan(lower_band.iloc[-1]) else current_vwap - current_atr

        # Skip first bar(s) of the day (VWAP not stable yet)
        bar_idx = self._get_bar_index_in_day(data)
        current_bar_in_day = int(bar_idx.iloc[-1])
        min_bars_from_open = self.params["min_bars_from_open"]

        if current_bar_in_day < min_bars_from_open:
            result.notes = f"Günün ilk {min_bars_from_open} barı atlanıyor (VWAP stabilize oluyor)"
            return result

        # Volume check
        vol_lookback = self.params["volume_lookback"]
        avg_volume = float(volume.iloc[-vol_lookback:].mean()) if len(volume) >= vol_lookback else float(volume.mean())
        volume_ok = current_volume >= avg_volume * self.params["volume_multiplier"]

        # Distance from VWAP as percentage
        vwap_distance_pct = ((current_price - current_vwap) / current_vwap) * 100
        touch_threshold = self.params["vwap_touch_threshold"]

        # Store VWAP data
        result.extra_data = {
            "vwap": round(current_vwap, 4),
            "upper_band": round(current_upper, 4),
            "lower_band": round(current_lower, 4),
            "vwap_distance_pct": round(vwap_distance_pct, 3),
            "current_volume": int(current_volume),
            "avg_volume": int(avg_volume),
            "volume_ratio": round(current_volume / avg_volume, 2) if avg_volume > 0 else 0,
            "volume_ok": volume_ok,
            "atr": round(current_atr, 4),
            "bar_in_day": current_bar_in_day,
        }

        # Set VWAP as peak/trough reference
        result.last_peak = current_upper
        result.last_trough = current_lower

        # ---- Determine trend direction ----
        use_trend_filter = self.params["trend_filter"]

        # Check if price touched VWAP recently (current or previous bar)
        prev_close = float(close.iloc[-2]) if len(close) > 1 else current_price
        prev_low = float(low.iloc[-2]) if len(low) > 1 else current_low
        prev_high = float(high.iloc[-2]) if len(high) > 1 else current_high
        prev_vwap = float(vwap.iloc[-2]) if len(vwap) > 1 else current_vwap

        # Touch detection: Did price reach within touch_threshold% of VWAP?
        touched_from_above = (current_low <= current_vwap * (1 + touch_threshold / 100))
        touched_from_below = (current_high >= current_vwap * (1 - touch_threshold / 100))

        # Previous bar also considered for multi-bar touches
        prev_touched_from_above = (prev_low <= prev_vwap * (1 + touch_threshold / 100))
        prev_touched_from_below = (prev_high >= prev_vwap * (1 - touch_threshold / 100))

        # Price in VWAP zone (between bands)?
        price_near_vwap = current_lower <= current_price <= current_upper

        # ---- PRECONDITION: Price near VWAP zone ----
        if not price_near_vwap and not touched_from_above and not touched_from_below:
            result.notes = f"Fiyat VWAP bölgesinden uzak ({vwap_distance_pct:+.2f}%)"
            return result

        result.precondition_met = True

        # ---- MAIN CONDITION: Bounce detected ----
        # LONG BOUNCE: price came down to VWAP and bounced up
        long_bounce = (
            (touched_from_above or prev_touched_from_above)  # Touched VWAP
            and current_price > current_vwap  # Currently above VWAP
            and close.iloc[-1] > close.iloc[-2]  # Closing higher than previous
        )

        # SHORT BOUNCE: price came up to VWAP and bounced down
        short_bounce = (
            (touched_from_below or prev_touched_from_below)  # Touched VWAP
            and current_price < current_vwap  # Currently below VWAP
            and close.iloc[-1] < close.iloc[-2]  # Closing lower than previous
        )

        # Apply trend filter
        if use_trend_filter:
            if current_price < current_vwap:
                long_bounce = False  # Don't go long below VWAP
            if current_price > current_vwap:
                short_bounce = False  # Don't go short above VWAP

        # Long-only mode (BIST spot: no retail intraday short selling)
        if self.long_only:
            short_bounce = False

        # === LONG BOUNCE ===
        if long_bounce and volume_ok:
            result.direction = "long"
            result.main_condition_met = True

            entry = current_price + buffer
            sl_level = current_lower - buffer  # VWAP -1σ as stop
            risk = entry - sl_level

            # Minimum risk check
            min_risk = current_atr * 0.3
            if risk < min_risk:
                sl_level = entry - min_risk
                risk = min_risk

            tp = entry + (risk * self.risk_reward_ratio)

            result.entry_price = round(entry, 4)
            result.stop_loss = round(sl_level, 4)
            result.take_profit = round(tp, 4)

            vol_ratio = round(current_volume / avg_volume, 1) if avg_volume > 0 else 0
            result.notes = f"VWAP Bounce yukarı ({vol_ratio}x hacim) → LONG"
            result.extra_data["bounce_type"] = "long"

        # === SHORT BOUNCE ===
        elif short_bounce and volume_ok:
            result.direction = "short"
            result.main_condition_met = True

            entry = current_price - buffer
            sl_level = current_upper + buffer  # VWAP +1σ as stop
            risk = sl_level - entry

            # Minimum risk check
            min_risk = current_atr * 0.3
            if risk < min_risk:
                sl_level = entry + min_risk
                risk = min_risk

            tp = entry - (risk * self.risk_reward_ratio)

            result.entry_price = round(entry, 4)
            result.stop_loss = round(sl_level, 4)
            result.take_profit = round(tp, 4)

            vol_ratio = round(current_volume / avg_volume, 1) if avg_volume > 0 else 0
            result.notes = f"VWAP Bounce aşağı ({vol_ratio}x hacim) → SHORT"
            result.extra_data["bounce_type"] = "short"

        # === NO BOUNCE YET ===
        elif long_bounce and not volume_ok:
            result.direction = "long"
            vol_ratio = round(current_volume / avg_volume, 1) if avg_volume > 0 else 0
            result.notes = f"VWAP Bounce yukarı tespit edildi ama hacim yetersiz ({vol_ratio}x)"

        elif short_bounce and not volume_ok:
            result.direction = "short"
            vol_ratio = round(current_volume / avg_volume, 1) if avg_volume > 0 else 0
            result.notes = f"VWAP Bounce aşağı tespit edildi ama hacim yetersiz ({vol_ratio}x)"

        else:
            result.notes = f"VWAP bölgesinde ({vwap_distance_pct:+.2f}%), bounce bekleniyor"

        result = self.annotate_trade_plan(data, result)
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
            vwap = result.extra_data.get("vwap", "?")
            dist = result.extra_data.get("vwap_distance_pct", 0)
            return f"⏳ VWAP bölgesinde ({dist:+.2f}%), bounce bekleniyor (VWAP: {vwap})"
        else:
            return "❌ VWAP bölgesinden uzak"
