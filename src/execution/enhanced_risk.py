"""
Enhanced risk management module for Cashflow trading system.

This module extends the base risk management with volatility-adjusted
position sizing and dynamic circuit breaker thresholds.
"""
import logging
from typing import Dict, Any, Optional
import numpy as np
from .risk import RiskManager
from ..strategy import Signal

class EnhancedRiskManager(RiskManager):
    """
    Enhanced risk manager with volatility-adjusted position sizing.
    
    Features:
    - Adjusts position sizes based on recent market volatility
    - Implements dynamic circuit breaker thresholds
    - Provides additional risk metrics
    """
    
    def __init__(self, config: Dict, data_manager=None):
        """
        Initialize the enhanced risk manager.
        
        Args:
            config: Risk configuration parameters
            data_manager: Reference to the data manager for market data access
        """
        super().__init__(config)
        self.data_manager = data_manager
        
        # Volatility adjustment parameters
        self.volatility_lookback = config.get("volatility_lookback", 14)  # days
        self.max_volatility_adjustment = config.get("max_volatility_adjustment", 0.3)  # 30% size reduction (reduced from 0.5 for more aggressive sizing)
        self.volatility_floor = config.get("volatility_floor", 0.01)  # 1% daily volatility
        self.volatility_ceiling = config.get("volatility_ceiling", 0.08)  # 8% daily volatility (increased from 0.05)
        
        # Dynamic circuit breaker parameters
        self.dynamic_circuit_breaker = config.get("dynamic_circuit_breaker", True)  # Enable dynamic circuit breakers
        self.base_drawdown_threshold = config.get("circuit_breaker_drawdown", 0.05)  # 5% daily drawdown limit
        
        self.logger = logging.getLogger("execution.enhanced_risk")
        
    def calculate_order_size(self, signal: Signal, order_book: Dict[str, Any], 
                           portfolio_value: float, current_position: float) -> float:
        """
        Calculate order size with volatility adjustment.
        
        Args:
            signal: Trading signal
            order_book: Current order book state
            portfolio_value: Current portfolio value
            current_position: Current position size
            
        Returns:
            Adjusted order size
        """
        # Get base size from parent class
        base_size = super().calculate_order_size(signal, order_book, portfolio_value, current_position)
        
        # Apply volatility adjustment if data manager is available
        if self.data_manager:
            volatility_factor = self._calculate_volatility_factor()
            adjusted_size = base_size * volatility_factor
            
            self.logger.info(f"Volatility adjustment: base_size={base_size:.4f}, " 
                           f"vol_factor={volatility_factor:.2f}, adjusted_size={adjusted_size:.4f}")
            
            return adjusted_size
        else:
            self.logger.warning("Data manager not available for volatility adjustment")
            return base_size
    
    def _calculate_volatility_factor(self) -> float:
        """
        Calculate position size adjustment based on recent market volatility.
        
        Returns:
            Adjustment factor between (1-max_adjustment) and 1.0
            1.0 = normal volatility, lower values = higher volatility
        """
        try:
            # Get recent volatility data
            recent_volatility = self._get_recent_volatility()
            
            # Normalize volatility (0-1 scale)
            normalized_vol = (recent_volatility - self.volatility_floor) / (self.volatility_ceiling - self.volatility_floor)
            normalized_vol = max(0, min(1, normalized_vol))  # clamp to 0-1
            
            # Higher volatility = smaller position size
            adjustment_factor = 1.0 - (normalized_vol * self.max_volatility_adjustment)
            
            self.logger.debug(f"Volatility: {recent_volatility:.4f}, normalized: {normalized_vol:.2f}, " 
                            f"adjustment: {adjustment_factor:.2f}")
            
            return adjustment_factor
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility factor: {e}")
            return 1.0  # Default to no adjustment on error
    
    def _get_recent_volatility(self) -> float:
        """
        Calculate recent price volatility.
        
        Returns:
            Annualized volatility as a decimal (e.g., 0.20 = 20%)
        """
        try:
            # Get daily candles from data manager
            df = self.data_manager.get_candles("1d", limit=self.volatility_lookback)
            
            # Calculate daily returns
            df['returns'] = df['c'].pct_change().fillna(0)
            
            # Calculate annualized volatility
            daily_vol = df['returns'].std()
            annualized_vol = daily_vol * np.sqrt(365)
            
            return annualized_vol
            
        except Exception as e:
            self.logger.error(f"Error calculating recent volatility: {e}")
            return 0.02  # Default to 2% volatility on error
    
    def update_circuit_breaker_threshold(self, recent_volatility: Optional[float] = None) -> float:
        """
        Update circuit breaker threshold based on recent market volatility.
        
        Args:
            recent_volatility: Recent market volatility (optional)
            
        Returns:
            Updated circuit breaker threshold
        """
        if not self.dynamic_circuit_breaker:
            return self.base_drawdown_threshold
            
        # Get volatility if not provided
        if recent_volatility is None:
            recent_volatility = self._get_recent_volatility()
            
        # Scale threshold based on volatility
        # Higher volatility = higher threshold to avoid false triggers
        volatility_ratio = recent_volatility / 0.02  # 0.02 = 2% baseline volatility
        adjusted_threshold = self.base_drawdown_threshold * volatility_ratio
        
        # Clamp to reasonable range
        min_threshold = self.base_drawdown_threshold * 0.5
        max_threshold = self.base_drawdown_threshold * 2.0
        adjusted_threshold = max(min_threshold, min(adjusted_threshold, max_threshold))
        
        self.logger.info(f"Dynamic circuit breaker: volatility={recent_volatility:.4f}, "
                       f"adjusted_threshold={adjusted_threshold:.4f}")
        
        return adjusted_threshold
        
    def should_trigger_circuit_breaker(self, daily_pnl: float, portfolio_value: float, 
                                     consecutive_losses: int) -> bool:
        """
        Check if circuit breaker should be triggered with dynamic threshold.
        
        Args:
            daily_pnl: Daily profit and loss
            portfolio_value: Current portfolio value
            consecutive_losses: Number of consecutive losses
            
        Returns:
            True if circuit breaker should be triggered, False otherwise
        """
        # Check consecutive losses
        if consecutive_losses >= self.circuit_breaker_consecutive_losses:
            self.logger.warning(f"Circuit breaker triggered: {consecutive_losses} consecutive losses")
            return True
            
        # Check drawdown with dynamic threshold
        daily_drawdown = abs(daily_pnl) / portfolio_value if portfolio_value > 0 else 0
        threshold = self.update_circuit_breaker_threshold() if self.dynamic_circuit_breaker else self.base_drawdown_threshold
        
        if daily_drawdown >= threshold and daily_pnl < 0:
            self.logger.warning(f"Circuit breaker triggered: drawdown {daily_drawdown:.2%} exceeds threshold {threshold:.2%}")
            return True
            
        return False
