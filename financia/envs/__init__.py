from gymnasium.envs.registration import register
from financia.envs.trading_env import TradingEnv

register(
    id='TradingEnv-v0',
    entry_point='financia.envs.trading_env:TradingEnv',
)
