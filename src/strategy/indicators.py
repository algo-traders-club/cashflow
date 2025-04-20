"""
Technical indicators for the Cashflow trading system.

This module implements various technical indicators used by the trading strategies.
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple

def calculate_rsi(df: pd.DataFrame, column: str = 'c', period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        df: DataFrame containing price data
        column: Column name to use for calculation
        period: RSI period
        
    Returns:
        Series containing RSI values
    """
    delta = df[column].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_bollinger_bands(df: pd.DataFrame, column: str = 'c', 
                            period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.
    
    Args:
        df: DataFrame containing price data
        column: Column name to use for calculation
        period: Bollinger Bands period
        std_dev: Number of standard deviations
        
    Returns:
        Tuple of (middle band, upper band, lower band)
    """
    middle_band = df[column].rolling(window=period).mean()
    std = df[column].rolling(window=period).std()
    
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return middle_band, upper_band, lower_band

def calculate_ema(df: pd.DataFrame, column: str = 'c', period: int = 20) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).
    
    Args:
        df: DataFrame containing price data
        column: Column name to use for calculation
        period: EMA period
        
    Returns:
        Series containing EMA values
    """
    return df[column].ewm(span=period, adjust=False).mean()

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    
    Args:
        df: DataFrame containing OHLC data
        period: ATR period
        
    Returns:
        Series containing ATR values
    """
    high_low = (df['h'] - df['l']).abs()
    high_close = (df['h'] - df['c'].shift()).abs()
    low_close = (df['l'] - df['c'].shift()).abs()
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    return true_range.rolling(period).mean()

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average Directional Index (ADX).
    
    Args:
        df: DataFrame containing OHLC data
        period: ADX period
        
    Returns:
        Series containing ADX values
    """
    # Calculate True Range
    high_low = (df['h'] - df['l']).abs()
    high_close = (df['h'] - df['c'].shift()).abs()
    low_close = (df['l'] - df['c'].shift()).abs()
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    # Calculate Directional Movement
    up_move = df['h'] - df['h'].shift()
    down_move = df['l'].shift() - df['l']
    
    # Calculate Directional Indicators
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    # Calculate Smoothed Directional Indicators
    tr_period = true_range.rolling(period).sum()
    plus_di = 100 * (pd.Series(plus_dm).rolling(period).sum() / tr_period)
    minus_di = 100 * (pd.Series(minus_dm).rolling(period).sum() / tr_period)
    
    # Calculate Directional Index
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
    
    # Calculate ADX
    adx = dx.rolling(period).mean()
    
    return adx

def calculate_macd(df: pd.DataFrame, column: str = 'c', 
                 fast_period: int = 12, slow_period: int = 26, 
                 signal_period: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Moving Average Convergence Divergence (MACD).
    
    Args:
        df: DataFrame containing price data
        column: Column name to use for calculation
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal EMA period
        
    Returns:
        Tuple of (MACD line, signal line, histogram)
    """
    fast_ema = df[column].ewm(span=fast_period, adjust=False).mean()
    slow_ema = df[column].ewm(span=slow_period, adjust=False).mean()
    
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram
