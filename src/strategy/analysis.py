"""
Signal analysis methods for the Cashflow trading system.

This module contains methods for analyzing market conditions and generating signals.
"""
import pandas as pd
from typing import Tuple
from .signal import SignalType

def check_mean_reversion(latest_1m: pd.Series, latest_5m: pd.Series, 
                        rsi_oversold: float, rsi_overbought: float) -> SignalType:
    """
    Check for mean reversion signals.
    
    Args:
        latest_1m: Latest 1-minute candle data with indicators
        latest_5m: Latest 5-minute candle data with indicators
        rsi_oversold: RSI threshold for oversold conditions
        rsi_overbought: RSI threshold for overbought conditions
        
    Returns:
        Signal type (BUY, SELL, or NEUTRAL)
    """
    # Check if price is outside Bollinger Bands
    price = latest_5m['c']  # Already using 'c' for close price
    bb_upper = latest_5m['bb_upper']
    bb_lower = latest_5m['bb_lower']
    
    # Check RSI conditions
    rsi = latest_1m['rsi']
    
    # Buy signal: Price below lower band and RSI oversold
    if price < bb_lower and rsi < rsi_oversold:
        return SignalType.BUY
        
    # Sell signal: Price above upper band and RSI overbought
    elif price > bb_upper and rsi > rsi_overbought:
        return SignalType.SELL
        
    # No signal
    return SignalType.NEUTRAL

def check_trend_confirmation(latest_5m: pd.Series, prev_5m: pd.Series, 
                           signal_type: SignalType, adx_threshold: float) -> bool:
    """
    Check if the trend confirms the mean reversion signal.
    
    Args:
        latest_5m: Latest 5-minute candle data with indicators
        prev_5m: Previous 5-minute candle data with indicators
        signal_type: Type of signal to confirm
        adx_threshold: ADX threshold for trend strength
        
    Returns:
        True if trend confirms the signal, False otherwise
    """
    if prev_5m is None:
        return False
        
    # Calculate EMA slope
    ema_slope = latest_5m['ema'] - prev_5m['ema']
    
    # Check ADX for trend strength
    adx = latest_5m['adx']
    trend_strong_enough = adx > adx_threshold
    
    # For buy signals, we want positive EMA slope
    if signal_type == SignalType.BUY:
        return ema_slope > 0 and trend_strong_enough
        
    # For sell signals, we want negative EMA slope
    elif signal_type == SignalType.SELL:
        return ema_slope < 0 and trend_strong_enough
        
    return False

def calculate_exit_levels(price: float, atr: float, signal_type: SignalType,
                        take_profit_multiple: float, stop_loss_multiple: float) -> Tuple[float, float]:
    """
    Calculate take profit and stop loss levels based on ATR.
    
    Args:
        price: Current price
        atr: Average True Range
        signal_type: Type of signal (BUY or SELL)
        take_profit_multiple: Multiple of ATR for take profit
        stop_loss_multiple: Multiple of ATR for stop loss
        
    Returns:
        Tuple of (take profit level, stop loss level)
    """
    if signal_type == SignalType.BUY:
        take_profit = price + (atr * take_profit_multiple)
        stop_loss = price - (atr * stop_loss_multiple)
    else:  # SELL
        take_profit = price - (atr * take_profit_multiple)
        stop_loss = price + (atr * stop_loss_multiple)
        
    return take_profit, stop_loss

def calculate_signal_strength(latest_1m: pd.Series, latest_5m: pd.Series, 
                            signal_type: SignalType, rsi_oversold: float, 
                            rsi_overbought: float) -> float:
    """
    Calculate signal strength based on indicator values.
    
    Args:
        latest_1m: Latest 1-minute candle data with indicators
        latest_5m: Latest 5-minute candle data with indicators
        signal_type: Type of signal (BUY or SELL)
        rsi_oversold: RSI threshold for oversold conditions
        rsi_overbought: RSI threshold for overbought conditions
        
    Returns:
        Signal strength (0.0 to 1.0)
    """
    rsi = latest_1m['rsi']
    price = latest_5m['c']
    bb_upper = latest_5m['bb_upper']
    bb_lower = latest_5m['bb_lower']
    
    if signal_type == SignalType.BUY:
        # How oversold is RSI (0-30 range)
        rsi_strength = (rsi_oversold - rsi) / rsi_oversold
        # How far below lower BB (normalized)
        bb_strength = (bb_lower - price) / bb_lower
        
    else:  # SELL
        # How overbought is RSI (70-100 range)
        rsi_strength = (rsi - rsi_overbought) / (100 - rsi_overbought)
        # How far above upper BB (normalized)
        bb_strength = (price - bb_upper) / bb_upper
        
    # Combine the two factors (equal weight)
    strength = (rsi_strength + bb_strength) / 2
    
    # Ensure it's in the 0.0 to 1.0 range
    return max(0.0, min(1.0, strength))
