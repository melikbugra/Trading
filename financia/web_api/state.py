"""
Global State Management for Web API
Holds singleton instances of ML models to avoid circular imports between main.py and routers.
"""

class AppState:
    bist100_engine = None
    binance_engine = None

# Single instance
state = AppState()
