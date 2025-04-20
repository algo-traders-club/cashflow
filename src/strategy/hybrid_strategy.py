"""
Hybrid trading strategy implementation for Cashflow.

This module implements a hybrid mean reversion and trend following strategy
for the USDC/HYPE trading pair on Hyperliquid.
"""
import logging
import pandas as pd
from typing import Dict, Tuple, Optional
from .signal import Signal, SignalType
from .indicators import (
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_atr,
    calculate_adx
)
from .analysis import (
    check_mean_reversion,
    check_trend_confirmation,
    calculate_exit_levels,
    calculate_signal_strength
)

class HybridStrategy:
    """
    Hybrid strategy combining mean reversion and trend following.
    
    Entry conditions:
    - Mean Reversion: Price deviates >1.5σ from 20-period Bollinger Bands on 5m candles
                     RSI(14) < 30 (long) or > 70 (short) on 1m candles
    - Trend Filter: Confirm with 50-period EMA slope (positive for longs, negative for shorts)
                   Optional: ADX(14) > 25 to ensure sufficient trend strength
    
    Exit conditions:
    - Take-profit at 1.5× ATR (14-period, 5m candles)
    - Stop-loss at 0.5× ATR or RSI reverting to neutral (40–60 range)
    - Time-based exit: Close position if no exit condition is met within 30 minutes
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the strategy with configuration parameters.
        
        Args:
            config: Strategy configuration parameters
        """
        # Mean reversion parameters
        self.bb_period = config.get("bb_period", 20)
        self.bb_std_dev = config.get("bb_std_dev", 1.5)
        self.rsi_period = config.get("rsi_period", 14)
        self.rsi_oversold = config.get("rsi_oversold", 30)
        self.rsi_overbought = config.get("rsi_overbought", 70)
        
        # Trend following parameters
        self.ema_period = config.get("ema_period", 50)
        self.adx_period = config.get("adx_period", 14)
        self.adx_threshold = config.get("adx_threshold", 25)
        
        # Exit parameters
        self.atr_period = config.get("atr_period", 14)
        self.take_profit_atr_multiple = config.get("take_profit_atr_multiple", 1.5)
        self.stop_loss_atr_multiple = config.get("stop_loss_atr_multiple", 0.5)
        
        self.logger = logging.getLogger("strategy.hybrid")
    
    def calculate_indicators(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Calculate technical indicators on the provided dataframes.
        
        Args:
            df_1m: 1-minute OHLCV data
            df_5m: 5-minute OHLCV data
            
        Returns:
            Tuple of DataFrames with indicators added
        """
        # Make a copy to avoid SettingWithCopyWarning
        df_1m = df_1m.copy()
        df_5m = df_5m.copy()
        
        # 1-minute indicators
        df_1m.loc[:, 'rsi'] = calculate_rsi(df_1m, 'c', self.rsi_period)
        
        # 5-minute indicators
        bb_middle, bb_upper, bb_lower = calculate_bollinger_bands(
            df_5m, 'c', self.bb_period, self.bb_std_dev
        )
        df_5m.loc[:, 'bb_middle'] = bb_middle
        df_5m.loc[:, 'bb_upper'] = bb_upper
        df_5m.loc[:, 'bb_lower'] = bb_lower
        df_5m.loc[:, 'ema'] = calculate_ema(df_5m, 'c', self.ema_period)
        df_5m.loc[:, 'atr'] = calculate_atr(df_5m, self.atr_period)
        df_5m.loc[:, 'adx'] = calculate_adx(df_5m, self.adx_period)
        
        return df_1m, df_5m
    
    def generate_signal(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame) -> Optional[Signal]:
        """
        Generate trading signals based on the strategy rules.
        
        Args:
            df_1m: 1-minute OHLCV data with indicators
            df_5m: 5-minute OHLCV data with indicators
            
        Returns:
            Signal object if a signal is generated, None otherwise
        """
        if df_1m.empty or df_5m.empty:
            return None
        
        # Get the latest data points
        latest_1m = df_1m.iloc[-1]
        latest_5m = df_5m.iloc[-1]
        prev_5m = df_5m.iloc[-2] if len(df_5m) > 1 else None
        
        # Current price
        current_price = latest_1m['c']
        
        # Check for mean reversion signals
        mean_reversion_signal = check_mean_reversion(
            latest_1m, 
            latest_5m, 
            self.rsi_oversold, 
            self.rsi_overbought
        )
        
        # If no mean reversion signal, return None
        if mean_reversion_signal == SignalType.NEUTRAL:
            return None
        
        # Check trend confirmation
        trend_confirmed = check_trend_confirmation(
            latest_5m, 
            prev_5m, 
            mean_reversion_signal, 
            self.adx_threshold
        )
        
        # If trend doesn't confirm, return None
        if not trend_confirmed:
            return None
        
        # Calculate exit levels
        atr = latest_5m['atr']
        take_profit, stop_loss = calculate_exit_levels(
            current_price, 
            atr, 
            mean_reversion_signal,
            self.take_profit_atr_multiple,
            self.stop_loss_atr_multiple
        )
        
        # Calculate signal strength (0.0 to 1.0)
        # This can be used for position sizing
        strength = calculate_signal_strength(
            latest_1m, 
            latest_5m, 
            mean_reversion_signal,
            self.rsi_oversold,
            self.rsi_overbought
        )
        
        # Create signal object
        signal = Signal(
            type=mean_reversion_signal,
            strength=strength,
            price=current_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            metadata={
                "rsi": latest_1m['rsi'],
                "bb_upper": latest_5m['bb_upper'],
                "bb_lower": latest_5m['bb_lower'],
                "ema": latest_5m['ema'],
                "adx": latest_5m['adx'],
                "atr": latest_5m['atr']
            }
        )
        
        self.logger.info(f"Generated signal: {signal}")
        return signal
