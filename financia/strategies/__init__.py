"""
Strategy-based trading system.
Supports both BIST100 and Binance markets.
"""

from .base import BaseStrategy, StrategyResult
from .ema_macd import EMAMACDStrategy

# Registry of available strategies
STRATEGY_REGISTRY = {
    "EMAMACDStrategy": EMAMACDStrategy,
}


def get_strategy_class(strategy_type: str):
    """Get strategy class by name."""
    return STRATEGY_REGISTRY.get(strategy_type)


def list_available_strategies():
    """List all available strategy types."""
    return list(STRATEGY_REGISTRY.keys())
