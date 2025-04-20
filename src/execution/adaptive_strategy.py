"""
Adaptive execution strategy for the Cashflow trading system.

This module implements an execution strategy that dynamically selects
the optimal order type based on market conditions.
"""
import logging
import time
from typing import Dict, Any, Optional, List
import numpy as np

from ..strategy import Signal
from .orders import Order, OrderType, OrderStatus
from .strategies import (
    ExecutionStrategy,
    MarketOrderStrategy,
    LimitOrderStrategy,
    TWAPStrategy,
    IcebergStrategy
)

class AdaptiveExecutionStrategy(ExecutionStrategy):
    """
    Dynamically selects the optimal execution strategy based on:
    - Current market liquidity
    - Order size relative to average volume
    - Recent price volatility
    
    This strategy aims to minimize market impact and slippage by
    choosing the most appropriate execution method for current conditions.
    """
    
    def __init__(self, exchange, data_manager=None, config: Dict = None):
        """
        Initialize the adaptive execution strategy.
        
        Args:
            exchange: Exchange interface for order execution
            data_manager: Data manager for market data access
            config: Configuration parameters
        """
        super().__init__(exchange)
        self.data_manager = data_manager
        self.config = config or {}
        
        # Sub-strategies
        self.market_strategy = MarketOrderStrategy(exchange)
        self.limit_strategy = LimitOrderStrategy(exchange)
        self.twap_strategy = TWAPStrategy(exchange)
        self.iceberg_strategy = IcebergStrategy(exchange)
        
        # Configuration
        self.min_liquidity_score = self.config.get("min_liquidity_score", 0.2)  # Reduced from 0.3 to allow trading in less liquid conditions
        self.max_volatility_for_market = self.config.get("max_volatility_for_market_orders", 0.9)  # Increased from 0.7 to allow market orders in more volatile conditions
        self.size_threshold_for_twap = self.config.get("size_threshold_for_twap", 0.02)  # Increased from 0.01 to 2% of avg volume
        
        self.logger = logging.getLogger("execution.adaptive_strategy")
        
    async def execute(self, signal: Signal, size: float, order_book: Dict[str, Any]) -> Optional[Order]:
        """
        Execute a trading signal using the optimal strategy for current conditions.
        
        Args:
            signal: Trading signal to execute
            size: Order size
            order_book: Current order book state
            
        Returns:
            Order object if order was placed, None otherwise
        """
        try:
            # Analyze market conditions
            liquidity_score = self._calculate_liquidity_score(order_book)
            volatility_score = self._calculate_volatility_score()
            size_ratio = self._calculate_size_ratio(size)
            
            self.logger.info(f"Market conditions: liquidity={liquidity_score:.2f}, "
                           f"volatility={volatility_score:.2f}, size_ratio={size_ratio:.4f}")
            
            # Select strategy based on conditions
            if size_ratio > self.size_threshold_for_twap or liquidity_score < self.min_liquidity_score:
                # Large order or low liquidity - use TWAP
                self.logger.info(f"Using TWAP strategy: size_ratio={size_ratio:.4f}, liquidity={liquidity_score:.2f}")
                return await self.twap_strategy.execute(signal, size, order_book)
                
            elif volatility_score > self.max_volatility_for_market:
                # High volatility - use limit orders with wider spread
                self.logger.info(f"Using limit strategy: volatility={volatility_score:.2f}")
                # Adjust limit price based on volatility
                spread_adjustment = min(1.0, volatility_score)  # 0-100% spread adjustment
                return await self._execute_limit_with_adjustment(signal, size, order_book, spread_adjustment)
                
            elif size_ratio > self.size_threshold_for_twap / 2:
                # Medium-sized order - use iceberg
                self.logger.info(f"Using iceberg strategy: size_ratio={size_ratio:.4f}")
                return await self.iceberg_strategy.execute(signal, size, order_book)
                
            else:
                # Normal conditions - use market order
                self.logger.info("Using market strategy: normal conditions")
                return await self.market_strategy.execute(signal, size, order_book)
                
        except Exception as e:
            self.logger.error(f"Error in adaptive execution: {e}")
            # Fall back to market order on error
            self.logger.info("Falling back to market order due to error")
            return await self.market_strategy.execute(signal, size, order_book)
    
    async def _execute_limit_with_adjustment(self, signal: Signal, size: float, 
                                          order_book: Dict[str, Any], spread_adjustment: float) -> Optional[Order]:
        """
        Execute a limit order with adjusted price based on volatility.
        
        Args:
            signal: Trading signal
            size: Order size
            order_book: Order book data
            spread_adjustment: Adjustment factor for limit price (0-1)
            
        Returns:
            Order object if placed successfully
        """
        # Get mid price
        mid_price = self._get_mid_price(order_book)
        
        # Calculate base spread as a percentage of price
        base_spread = 0.0005  # 5 basis points
        
        # Adjust spread based on volatility
        adjusted_spread = base_spread * (1 + spread_adjustment * 4)  # Up to 5x wider
        
        # Calculate limit price
        if signal.type.value == "buy":
            # For buys, limit price is below mid price
            limit_price = mid_price * (1 - adjusted_spread)
        else:
            # For sells, limit price is above mid price
            limit_price = mid_price * (1 + adjusted_spread)
            
        self.logger.info(f"Adjusted limit price: mid={mid_price:.4f}, "
                       f"spread={adjusted_spread:.4%}, limit={limit_price:.4f}")
        
        # Create modified signal with limit price
        limit_signal = Signal(
            type=signal.type,
            strength=signal.strength,
            price=limit_price,
            take_profit=signal.take_profit,
            stop_loss=signal.stop_loss
        )
        
        # Execute with limit strategy
        return await self.limit_strategy.execute(limit_signal, size, order_book)
    
    def _calculate_liquidity_score(self, order_book: Dict[str, Any]) -> float:
        """
        Calculate liquidity score (0-1) based on order book depth.
        Higher score = more liquidity.
        
        Args:
            order_book: Order book data
            
        Returns:
            Liquidity score between 0 and 1
        """
        try:
            # Extract bids and asks
            bids = order_book.get("bids", [])
            asks = order_book.get("asks", [])
            
            if not bids or not asks:
                return 0.5  # Default if no data
                
            # Calculate total volume within 0.5% of mid price
            mid_price = self._get_mid_price(order_book)
            price_range = mid_price * 0.005  # 0.5%
            
            bid_volume = sum([bid[1] for bid in bids if mid_price - bid[0] <= price_range])
            ask_volume = sum([ask[1] for ask in asks if ask[0] - mid_price <= price_range])
            
            total_volume = bid_volume + ask_volume
            
            # Normalize against expected volume
            expected_volume = 100.0  # Baseline expected volume
            liquidity_score = min(1.0, total_volume / expected_volume)
            
            return liquidity_score
            
        except Exception as e:
            self.logger.error(f"Error calculating liquidity score: {e}")
            return 0.5  # Default on error
    
    def _calculate_volatility_score(self) -> float:
        """
        Calculate volatility score (0-1) based on recent price movements.
        Higher score = more volatility.
        
        Returns:
            Volatility score between 0 and 1
        """
        try:
            if not self.data_manager:
                return 0.5  # Default if no data manager
                
            # Get recent 1-minute candles
            df = self.data_manager.get_candles("1m", limit=30)
            
            if df.empty:
                return 0.5  # Default if no data
                
            # Calculate price range as percentage of average price
            price_range = (df['h'].max() - df['l'].min()) / df['c'].mean()
            
            # Normalize to 0-1 scale
            # 0.5% range = 0.25 score, 1% range = 0.5 score, 2% range = 1.0 score
            volatility_score = min(1.0, price_range / 0.02)
            
            return volatility_score
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility score: {e}")
            return 0.5  # Default on error
    
    def _calculate_size_ratio(self, size: float) -> float:
        """
        Calculate ratio of order size to average volume.
        
        Args:
            size: Order size
            
        Returns:
            Ratio of order size to average volume
        """
        try:
            if not self.data_manager:
                return 0.0  # Default if no data manager
                
            # Get recent 5-minute candles
            df = self.data_manager.get_candles("5m", limit=12)  # Last hour
            
            if df.empty:
                return 0.0  # Default if no data
                
            # Calculate average volume
            avg_volume = df['v'].mean()
            
            # Calculate size ratio
            size_ratio = size / avg_volume if avg_volume > 0 else 0.0
            
            return size_ratio
            
        except Exception as e:
            self.logger.error(f"Error calculating size ratio: {e}")
            return 0.0  # Default on error
    
    def _get_mid_price(self, order_book: Dict[str, Any]) -> float:
        """
        Calculate mid price from order book.
        
        Args:
            order_book: Order book data
            
        Returns:
            Mid price
        """
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        
        if not bids or not asks:
            return 0.0
            
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        
        if best_bid <= 0 or best_ask <= 0:
            return 0.0
            
        return (best_bid + best_ask) / 2
