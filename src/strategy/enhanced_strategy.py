"""
Enhanced hybrid strategy for the Cashflow trading system.

This module extends the base hybrid strategy with volume confirmation,
time-of-day filters, and additional signal quality checks.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

from ..strategy import HybridStrategy, Signal, SignalType

class EnhancedHybridStrategy(HybridStrategy):
    """
    Enhanced hybrid strategy with additional filters and confirmations.
    
    Features:
    - Volume confirmation for signals
    - Time-of-day filters to avoid low-quality trading periods
    - Market regime detection
    - Signal strength normalization
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the enhanced hybrid strategy.
        
        Args:
            config: Strategy configuration parameters
        """
        super().__init__(config)
        self.config = config or {}
        
        # Volume confirmation parameters
        self.volume_confirmation = self.config.get("volume_confirmation", True)
        self.volume_lookback = self.config.get("volume_lookback", 5)  # candles
        self.volume_threshold = self.config.get("volume_threshold", 1.25)  # 125% of average (reduced from 1.5 for more signals)
        
        # Time filter parameters
        self.time_filters_enabled = self.config.get("time_filters_enabled", True)
        self.avoid_news_events = self.config.get("avoid_news_events", True)
        self.low_liquidity_hours = self.config.get("low_liquidity_hours", [0, 1, 2, 3])  # UTC hours
        
        # Market regime parameters
        self.regime_detection = self.config.get("regime_detection", True)
        self.trend_lookback = self.config.get("trend_lookback", 20)  # candles
        
        self.logger = logging.getLogger("strategy.enhanced")
        
    def generate_signal(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame) -> Optional[Signal]:
        """
        Generate trading signal with additional filters.
        
        Args:
            df_1m: 1-minute candle data
            df_5m: 5-minute candle data
            
        Returns:
            Trading signal if conditions are met, None otherwise
        """
        # Generate base signal
        signal = super().generate_signal(df_1m, df_5m)
        
        # Record signal opportunity for metrics tracking if we have a metrics collector
        if signal and hasattr(self, 'metrics_collector') and self.metrics_collector:
            self.metrics_collector.record_signal_opportunity(signal.signal_type.value, signal.strength)
        
        if not signal:
            return None
            
        # Apply additional filters
        if self.volume_confirmation and not self._check_volume_confirmation(df_1m, df_5m, signal.signal_type):
            self.logger.info(f"Signal rejected due to insufficient volume confirmation")
            return None
            
        if self.time_filters_enabled and not self._check_time_filter():
            self.logger.info(f"Signal rejected due to time filter")
            return None
            
        if self.regime_detection and not self._check_market_regime(df_5m, signal.signal_type):
            self.logger.info(f"Signal rejected due to unfavorable market regime")
            return None
            
        # Adjust signal strength based on multiple factors
        signal.strength = self._adjust_signal_strength(signal, df_1m, df_5m)
        
        # Increase signal strength by 20% to be more aggressive
        signal.strength = min(1.0, signal.strength * 1.2)
        
        self.logger.info(f"Enhanced signal: {signal.signal_type.value} at {signal.price:.4f}, "
                       f"strength adjusted to {signal.strength:.2f}")
        
        return signal
        
    def _check_volume_confirmation(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame, signal_type: SignalType) -> bool:
        """
        Check if volume confirms the signal:
        - For buys: increasing volume on up moves
        - For sells: increasing volume on down moves
        
        Args:
            df_1m: 1-minute candle data
            df_5m: 5-minute candle data
            signal_type: Type of signal (buy/sell)
            
        Returns:
            True if volume confirms signal, False otherwise
        """
        try:
            # Use 5-minute data for volume analysis
            if df_5m.empty or len(df_5m) < self.volume_lookback + 1:
                return True  # Not enough data, default to True
                
            # Get recent candles
            recent_candles = df_5m.tail(self.volume_lookback + 1)
            
            # Calculate price change and volume change
            recent_candles['price_change'] = recent_candles['c'].diff()
            recent_candles['volume_change'] = recent_candles['v'].diff()
            
            # Calculate average volume
            avg_volume = recent_candles['v'].mean()
            latest_volume = recent_candles['v'].iloc[-1]
            
            # Check if latest volume is above threshold
            volume_above_avg = latest_volume > (avg_volume * self.volume_threshold)
            
            if not volume_above_avg:
                self.logger.info(f"Volume below threshold: latest={latest_volume:.2f}, "
                               f"avg={avg_volume:.2f}, threshold={avg_volume * self.volume_threshold:.2f}")
                return False
                
            # For buy signals, check for increasing volume on up moves
            if signal_type == SignalType.BUY:
                # Get recent up candles
                up_candles = recent_candles[recent_candles['price_change'] > 0]
                
                if len(up_candles) < 2:
                    return True  # Not enough up candles, default to True
                    
                # Check if volume is increasing on up moves
                avg_up_volume = up_candles['v'].mean()
                latest_up_volume = up_candles['v'].iloc[-1] if not up_candles.empty else 0
                
                return latest_up_volume > avg_up_volume
                
            # For sell signals, check for increasing volume on down moves
            elif signal_type == SignalType.SELL:
                # Get recent down candles
                down_candles = recent_candles[recent_candles['price_change'] < 0]
                
                if len(down_candles) < 2:
                    return True  # Not enough down candles, default to True
                    
                # Check if volume is increasing on down moves
                avg_down_volume = down_candles['v'].mean()
                latest_down_volume = down_candles['v'].iloc[-1] if not down_candles.empty else 0
                
                return latest_down_volume > avg_down_volume
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error in volume confirmation: {e}")
            return True  # Default to True on error
        
    def _check_time_filter(self) -> bool:
        """
        Filter out low-probability times:
        - Avoid trading around major news events
        - Reduce activity during low-liquidity periods
        
        Returns:
            True if current time passes filters, False otherwise
        """
        try:
            # Get current UTC time
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            
            # Check for low liquidity hours
            if current_hour in self.low_liquidity_hours:
                self.logger.info(f"Current hour {current_hour} UTC is in low liquidity hours")
                return False
                
            # TODO: Add news event calendar integration
            # For now, just use time-based filters
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in time filter: {e}")
            return True  # Default to True on error
        
    def _check_market_regime(self, df_5m: pd.DataFrame, signal_type: SignalType) -> bool:
        """
        Check if the signal aligns with the current market regime.
        
        Args:
            df_5m: 5-minute candle data
            signal_type: Type of signal (buy/sell)
            
        Returns:
            True if signal aligns with market regime, False otherwise
        """
        try:
            if not self.regime_detection or df_5m.empty or len(df_5m) < self.trend_lookback:
                return True  # Not enough data or regime detection disabled
                
            # Calculate simple trend indicator (EMA20 vs EMA50)
            if 'ema20' not in df_5m.columns or 'ema50' not in df_5m.columns:
                df_5m['ema20'] = df_5m['c'].ewm(span=20, adjust=False).mean()
                df_5m['ema50'] = df_5m['c'].ewm(span=50, adjust=False).mean()
                
            # Determine market regime
            latest = df_5m.iloc[-1]
            trend_up = latest['ema20'] > latest['ema50']
            
            # Calculate ADX for trend strength
            if 'adx' not in df_5m.columns:
                # Simple ADX calculation (placeholder)
                df_5m['adx'] = 25  # Default value
                
            strong_trend = latest['adx'] > 25
            
            # In strong uptrend, favor buy signals
            if trend_up and strong_trend and signal_type == SignalType.BUY:
                return True
                
            # In strong downtrend, favor sell signals
            if not trend_up and strong_trend and signal_type == SignalType.SELL:
                return True
                
            # In weak trend, allow both signal types
            if not strong_trend:
                return True
                
            # Signal doesn't align with strong trend
            self.logger.info(f"Signal {signal_type.value} doesn't align with market regime: "
                           f"trend_up={trend_up}, strong_trend={strong_trend}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error in market regime check: {e}")
            return True  # Default to True on error
        
    def _adjust_signal_strength(self, signal: Signal, df_1m: pd.DataFrame, df_5m: pd.DataFrame) -> float:
        """
        Adjust signal strength based on multiple factors.
        
        Args:
            signal: Base signal
            df_1m: 1-minute candle data
            df_5m: 5-minute candle data
            
        Returns:
            Adjusted signal strength
        """
        try:
            base_strength = signal.strength
            adjustments = []
            
            # Adjust based on volume
            if not df_5m.empty:
                latest_volume = df_5m['v'].iloc[-1]
                avg_volume = df_5m['v'].tail(10).mean()
                volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 1.0
                volume_adj = min(0.2, max(-0.2, (volume_ratio - 1.0) * 0.2))
                adjustments.append(volume_adj)
                
            # Adjust based on trend alignment
            if not df_5m.empty and 'ema20' in df_5m.columns and 'ema50' in df_5m.columns:
                latest = df_5m.iloc[-1]
                trend_up = latest['ema20'] > latest['ema50']
                
                if (signal.type == SignalType.BUY and trend_up) or \
                   (signal.type == SignalType.SELL and not trend_up):
                    adjustments.append(0.1)  # Signal aligns with trend
                else:
                    adjustments.append(-0.1)  # Signal against trend
                    
            # Apply adjustments
            adjusted_strength = base_strength
            for adj in adjustments:
                adjusted_strength += adj
                
            # Ensure strength is between 0 and 1
            adjusted_strength = max(0.1, min(1.0, adjusted_strength))
            
            return adjusted_strength
            
        except Exception as e:
            self.logger.error(f"Error adjusting signal strength: {e}")
            return signal.strength  # Return original on error
