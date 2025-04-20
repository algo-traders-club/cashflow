"""
Agent module for the Cashflow trading system.

This module implements the main trading agent that coordinates data, strategy,
and execution components.
"""
from .trading_agent import TradingAgent
from .trading_loop import TradingLoop

__all__ = [
    'TradingAgent',
    'TradingLoop'
]
