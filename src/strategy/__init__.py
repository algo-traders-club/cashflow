"""
Strategy module for the Cashflow trading system.

This module implements trading strategies for the USDC/HYPE trading pair.
"""
from .signal import Signal, SignalType
from .hybrid_strategy import HybridStrategy
from .indicators import (
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_atr,
    calculate_adx,
    calculate_macd
)
from .analysis import (
    check_mean_reversion,
    check_trend_confirmation,
    calculate_exit_levels,
    calculate_signal_strength
)

__all__ = [
    'Signal',
    'SignalType',
    'HybridStrategy',
    'calculate_rsi',
    'calculate_bollinger_bands',
    'calculate_ema',
    'calculate_atr',
    'calculate_adx',
    'calculate_macd',
    'check_mean_reversion',
    'check_trend_confirmation',
    'calculate_exit_levels',
    'calculate_signal_strength'
]
