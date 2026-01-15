"""
Indicator Configuration System

Market and timeframe-aware indicator parameters based on
comprehensive research and best practices.

Usage:
    from financia.indicator_config import get_config
    
    config = get_config('binance', 'short')
    rsi_period = config['rsi']['period']
"""

# Timeframe mappings for each market
TIMEFRAME_INTERVALS = {
    'bist100': {
        'short': '1h',      # Hourly (intraday)
        'short-mid': '4h',  # 4-hour (swing)
        'medium': '1d',     # Daily
        'long': '1wk',      # Weekly
    },
    'binance': {
        'short': '1m',      # 1-minute (scalping)
        'mid': '15m',       # 15-minute (day trading)
        'long': '4h',       # 4-hour (swing)
    }
}

# Data fetching periods
DATA_PERIODS = {
    'bist100': {
        'short': '730d',    # 2 years of hourly
        'short-mid': '730d',
        'medium': '10y',
        'long': 'max',
    },
    'binance': {
        'short': 7,         # 7 days of 1m data (~10k candles)
        'mid': 60,          # 60 days of 15m data (~5.7k candles)
        'long': 365,        # 365 days of 4h data (~2.2k candles)
    }
}

# =============================================================================
# BIST100 CONFIGURATIONS
# =============================================================================

BIST100_SHORT = {
    # 1-hour timeframe (intraday trading)
    'rsi': {
        'period': 14,
        'overbought': 70,
        'oversold': 30,
    },
    'macd': {
        'fast': 12,
        'slow': 26,
        'signal': 9,
    },
    'bollinger': {
        'period': 20,
        'std': 2.0,
    },
    'adx': {
        'period': 14,
        'trend_threshold': 20,
        'strong_threshold': 25,
    },
    'ichimoku': {
        'tenkan': 9,
        'kijun': 26,
        'senkou_b': 52,
        'shift': 26,
    },
    'stochastic': {
        'k_period': 14,
        'k_smooth': 3,
        'd_period': 3,
        'overbought': 80,
        'oversold': 20,
    },
    'mfi': {
        'period': 14,
        'overbought': 80,
        'oversold': 20,
    },
    'cmf': {
        'period': 20,
        'buy_threshold': 0.05,
        'sell_threshold': -0.05,
    },
    'wavetrend': {
        'n1': 10,  # Channel length
        'n2': 21,  # Average length
        'overbought': 60,
        'oversold': -60,
    },
    'alligator': {
        'jaw_period': 13,
        'jaw_shift': 8,
        'teeth_period': 8,
        'teeth_shift': 5,
        'lips_period': 5,
        'lips_shift': 3,
    },
    'awesome': {
        'fast': 5,
        'slow': 34,
    },
    'sar': {
        'step': 0.02,
        'max_step': 0.20,
    },
    'volume_ma': {
        'period': 20,
    },
    'divergence': {
        'lookback': 60,
    },
}

BIST100_MEDIUM = {
    # Daily timeframe (swing trading)
    'rsi': {
        'period': 14,
        'overbought': 70,
        'oversold': 30,
    },
    'macd': {
        'fast': 12,
        'slow': 26,
        'signal': 9,
    },
    'bollinger': {
        'period': 20,
        'std': 2.0,
    },
    'adx': {
        'period': 14,
        'trend_threshold': 20,
        'strong_threshold': 25,
    },
    'ichimoku': {
        'tenkan': 9,
        'kijun': 26,
        'senkou_b': 52,
        'shift': 26,
    },
    'stochastic': {
        'k_period': 14,
        'k_smooth': 3,
        'd_period': 3,
        'overbought': 80,
        'oversold': 20,
    },
    'mfi': {
        'period': 14,
        'overbought': 80,
        'oversold': 20,
    },
    'cmf': {
        'period': 20,
        'buy_threshold': 0.05,
        'sell_threshold': -0.05,
    },
    'wavetrend': {
        'n1': 10,
        'n2': 21,
        'overbought': 60,
        'oversold': -60,
    },
    'alligator': {
        'jaw_period': 13,
        'jaw_shift': 8,
        'teeth_period': 8,
        'teeth_shift': 5,
        'lips_period': 5,
        'lips_shift': 3,
    },
    'awesome': {
        'fast': 5,
        'slow': 34,
    },
    'sar': {
        'step': 0.02,
        'max_step': 0.20,
    },
    'volume_ma': {
        'period': 20,
    },
    'divergence': {
        'lookback': 60,
    },
}

# =============================================================================
# BINANCE (CRYPTO) CONFIGURATIONS
# =============================================================================

BINANCE_SHORT = {
    # 1-minute timeframe (scalping/ultra-fast)
    'rsi': {
        'period': 5,        # Ultra-fast for 1m
        'overbought': 80,   # Wider bands for volatility
        'oversold': 20,
    },
    'macd': {
        'fast': 3,          # Ultra-fast MACD
        'slow': 10,
        'signal': 16,
    },
    'bollinger': {
        'period': 10,       # Shorter period
        'std': 1.5,         # Tighter bands
    },
    'adx': {
        'period': 7,        # Ultra-fast trend detection
        'trend_threshold': 20,
        'strong_threshold': 25,
    },
    'ichimoku': {
        'tenkan': 6,        # Fast conversion
        'kijun': 13,
        'senkou_b': 26,
        'shift': 13,
    },
    'stochastic': {
        'k_period': 5,      # Ultra-fast stochastic
        'k_smooth': 2,
        'd_period': 2,
        'overbought': 80,
        'oversold': 20,
    },
    'mfi': {
        'period': 7,        # Fast MFI
        'overbought': 80,
        'oversold': 20,
    },
    'cmf': {
        'period': 10,       # Shorter period
        'buy_threshold': 0.05,
        'sell_threshold': -0.05,
    },
    'wavetrend': {
        'n1': 5,            # Fast channel
        'n2': 10,           # Fast average
        'overbought': 60,
        'oversold': -60,
    },
    'alligator': {
        'jaw_period': 8,    # Faster alligator
        'jaw_shift': 5,
        'teeth_period': 5,
        'teeth_shift': 3,
        'lips_period': 3,
        'lips_shift': 2,
    },
    'awesome': {
        'fast': 3,          # Ultra-fast AO
        'slow': 21,
    },
    'sar': {
        'step': 0.025,      # Slightly faster SAR
        'max_step': 0.25,
    },
    'volume_ma': {
        'period': 10,
    },
    'divergence': {
        'lookback': 30,     # Shorter lookback for fast market
    },
}

BINANCE_MID = {
    # 15-minute timeframe (day trading)
    'rsi': {
        'period': 9,
        'overbought': 75,
        'oversold': 25,
    },
    'macd': {
        'fast': 8,
        'slow': 17,
        'signal': 9,
    },
    'bollinger': {
        'period': 15,
        'std': 2.0,
    },
    'adx': {
        'period': 10,
        'trend_threshold': 20,
        'strong_threshold': 25,
    },
    'ichimoku': {
        'tenkan': 7,
        'kijun': 22,
        'senkou_b': 44,
        'shift': 22,
    },
    'stochastic': {
        'k_period': 9,
        'k_smooth': 3,
        'd_period': 3,
        'overbought': 80,
        'oversold': 20,
    },
    'mfi': {
        'period': 10,
        'overbought': 80,
        'oversold': 20,
    },
    'cmf': {
        'period': 15,
        'buy_threshold': 0.05,
        'sell_threshold': -0.05,
    },
    'wavetrend': {
        'n1': 8,
        'n2': 17,
        'overbought': 60,
        'oversold': -60,
    },
    'alligator': {
        'jaw_period': 10,
        'jaw_shift': 6,
        'teeth_period': 6,
        'teeth_shift': 4,
        'lips_period': 4,
        'lips_shift': 2,
    },
    'awesome': {
        'fast': 4,
        'slow': 28,
    },
    'sar': {
        'step': 0.02,
        'max_step': 0.22,
    },
    'volume_ma': {
        'period': 15,
    },
    'divergence': {
        'lookback': 45,
    },
}

BINANCE_LONG = {
    # 4-hour timeframe (swing trading)
    'rsi': {
        'period': 14,
        'overbought': 70,
        'oversold': 30,
    },
    'macd': {
        'fast': 12,
        'slow': 26,
        'signal': 9,
    },
    'bollinger': {
        'period': 20,
        'std': 2.0,
    },
    'adx': {
        'period': 14,
        'trend_threshold': 20,
        'strong_threshold': 25,
    },
    'ichimoku': {
        'tenkan': 10,
        'kijun': 30,
        'senkou_b': 60,
        'shift': 30,
    },
    'stochastic': {
        'k_period': 14,
        'k_smooth': 3,
        'd_period': 3,
        'overbought': 80,
        'oversold': 20,
    },
    'mfi': {
        'period': 14,
        'overbought': 80,
        'oversold': 20,
    },
    'cmf': {
        'period': 20,
        'buy_threshold': 0.05,
        'sell_threshold': -0.05,
    },
    'wavetrend': {
        'n1': 10,
        'n2': 21,
        'overbought': 60,
        'oversold': -60,
    },
    'alligator': {
        'jaw_period': 13,
        'jaw_shift': 8,
        'teeth_period': 8,
        'teeth_shift': 5,
        'lips_period': 5,
        'lips_shift': 3,
    },
    'awesome': {
        'fast': 5,
        'slow': 34,
    },
    'sar': {
        'step': 0.02,
        'max_step': 0.20,
    },
    'volume_ma': {
        'period': 20,
    },
    'divergence': {
        'lookback': 60,
    },
}

# =============================================================================
# CONFIG REGISTRY
# =============================================================================

INDICATOR_CONFIGS = {
    'bist100': {
        'short': BIST100_SHORT,
        'short-mid': BIST100_SHORT,  # Same as short for now
        'medium': BIST100_MEDIUM,
        'long': BIST100_MEDIUM,      # Same as medium for now
    },
    'binance': {
        'short': BINANCE_SHORT,
        'mid': BINANCE_MID,
        'long': BINANCE_LONG,
    }
}


def get_config(market: str = 'bist100', horizon: str = 'short') -> dict:
    """
    Get indicator configuration for a specific market and horizon.
    
    Args:
        market: 'bist100' or 'binance'
        horizon: 'short', 'mid'/'short-mid', 'medium', 'long'
    
    Returns:
        Dictionary with all indicator parameters
    """
    market = market.lower()
    horizon = horizon.lower()
    
    if market not in INDICATOR_CONFIGS:
        print(f"Warning: Unknown market '{market}', falling back to bist100")
        market = 'bist100'
    
    if horizon not in INDICATOR_CONFIGS[market]:
        # Try to find a close match
        if horizon == 'short-mid' and 'mid' in INDICATOR_CONFIGS[market]:
            horizon = 'mid'
        elif horizon == 'mid' and 'short-mid' in INDICATOR_CONFIGS[market]:
            horizon = 'short-mid'
        else:
            print(f"Warning: Unknown horizon '{horizon}' for {market}, falling back to short")
            horizon = 'short'
    
    return INDICATOR_CONFIGS[market][horizon]


def get_interval(market: str = 'bist100', horizon: str = 'short') -> str:
    """Get the data interval for a market/horizon combination."""
    market = market.lower()
    horizon = horizon.lower()
    
    if market in TIMEFRAME_INTERVALS and horizon in TIMEFRAME_INTERVALS[market]:
        return TIMEFRAME_INTERVALS[market][horizon]
    
    # Default fallbacks
    if market == 'binance':
        return '1m'
    return '1h'


def get_data_period(market: str = 'bist100', horizon: str = 'short'):
    """Get the data period for a market/horizon combination."""
    market = market.lower()
    horizon = horizon.lower()
    
    if market in DATA_PERIODS and horizon in DATA_PERIODS[market]:
        return DATA_PERIODS[market][horizon]
    
    # Default fallbacks
    if market == 'binance':
        return 7  # days
    return '730d'
