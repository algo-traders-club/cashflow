"""
Execution engine for the Cashflow trading system.

This module handles order execution with liquidity-adaptive strategies.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from hyperliquid.exchange import Exchange
from ..strategy import Signal, SignalType
from .orders import Order, OrderType, OrderStatus
from .strategies import (
    MarketOrderStrategy,
    LimitOrderStrategy,
    TWAPStrategy,
    IcebergStrategy
)
from .risk import RiskManager, OrderMonitor

class ExecutionEngine:
    """
    Handles order execution with liquidity-adaptive strategies.
    
    Features:
    - Dynamically adjust order size based on order book depth
    - Use TWAP for large orders to minimize slippage
    - Implement iceberg orders for large positions
    - Monitor and manage open orders
    """
    
    def __init__(self, private_key: str, config: Dict):
        """
        Initialize the execution engine.
        
        Args:
            private_key: Hyperliquid private key
            config: Execution configuration parameters
        """
        # Create a wallet from the private key
        from eth_account import Account
        wallet = Account.from_key(private_key)
        self.exchange = Exchange(wallet=wallet)
        self.config = config
        
        # Risk parameters
        self.max_position_size = config.get("max_position_size", 0.1)  # 10% of portfolio
        self.max_trade_risk = config.get("max_trade_risk", 0.01)  # 1% per trade
        self.circuit_breaker_drawdown = config.get("circuit_breaker_drawdown", 0.05)  # 5% daily drawdown
        self.circuit_breaker_consecutive_losses = config.get("circuit_breaker_consecutive_losses", 3)
        
        # Execution parameters
        self.twap_volume_threshold = config.get("twap_volume_threshold", 0.005)  # 0.5% of average volume
        self.iceberg_size_threshold = config.get("iceberg_size_threshold", 0.01)  # 1% of portfolio
        self.stale_order_timeout = config.get("stale_order_timeout", 300)  # 5 minutes
        
        # State tracking
        self.open_orders = {}  # order_id -> Order
        self.positions = {}  # symbol -> position size
        self.portfolio_value = config.get("initial_portfolio_value", 1000.0)
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.trading_enabled = True
        
        # Execution strategies
        self.market_strategy = MarketOrderStrategy(self.exchange)
        self.limit_strategy = LimitOrderStrategy(self.exchange)
        self.twap_strategy = TWAPStrategy(self.exchange)
        self.iceberg_strategy = IcebergStrategy(self.exchange)
        
        # Risk management
        self.risk_manager = RiskManager(config)
        
        # Order monitoring
        self.order_monitor = OrderMonitor(
            self.exchange, 
            self.open_orders, 
            self.stale_order_timeout
        )
        
        # Tasks
        self._order_monitor_task = None
        
        self.logger = logging.getLogger("execution.engine")
    
    async def initialize(self):
        """Initialize the execution engine"""
        # Start order monitoring task
        self._order_monitor_task = asyncio.create_task(self.order_monitor.monitor_orders())
        self.logger.info("ExecutionEngine initialized")
    
    async def execute_signal(self, signal: Signal, order_book: Dict[str, Any]) -> Optional[Order]:
        """
        Execute a trading signal with liquidity-adaptive sizing.
        
        Args:
            signal: Trading signal to execute
            order_book: Current order book state
            
        Returns:
            Order object if order was placed, None otherwise
        """
        if not self.trading_enabled:
            self.logger.warning("Trading is disabled (circuit breaker triggered)")
            return None
        
        # Check if we can take this trade based on risk parameters
        if not self._check_risk_parameters(signal):
            return None
        
        # Determine order size based on signal strength and liquidity
        current_position = self.positions.get("HYPE/USDC", 0.0)
        size = self.risk_manager.calculate_order_size(
            signal, 
            order_book, 
            self.portfolio_value, 
            current_position
        )
        
        # Determine execution strategy based on signal, size and market conditions
        execution_strategy = self._determine_execution_strategy(signal, size, order_book)
        
        # Execute the order using the appropriate strategy
        order = None
        if execution_strategy == OrderType.MARKET:
            order = await self.market_strategy.execute(signal, size, order_book)
        elif execution_strategy == OrderType.LIMIT:
            order = await self.limit_strategy.execute(signal, size, order_book)
        elif execution_strategy == OrderType.TWAP:
            order = await self.twap_strategy.execute(signal, size, order_book)
        elif execution_strategy == OrderType.ICEBERG:
            order = await self.iceberg_strategy.execute(signal, size, order_book)
        
        # Add to open orders if order was placed
        if order:
            self.open_orders[order.order_id] = order
            
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: ID of the order to cancel
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        if order_id not in self.open_orders:
            self.logger.warning(f"Order {order_id} not found in open orders")
            return False
        
        try:
            result = self.exchange.cancel("HYPE/USDC", [order_id])
            
            if result and "success" in result and result["success"]:
                self.open_orders[order_id].status = OrderStatus.CANCELLED
                self.open_orders[order_id].updated_at = time.time()
                self.logger.info(f"Cancelled order {order_id}")
                return True
            else:
                self.logger.error(f"Failed to cancel order {order_id}: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def close_position(self, symbol: str) -> bool:
        """
        Close an open position.
        
        Args:
            symbol: Symbol of the position to close
            
        Returns:
            True if position was closed successfully, False otherwise
        """
        if symbol not in self.positions or self.positions[symbol] == 0:
            self.logger.warning(f"No open position for {symbol}")
            return False
        
        position_size = self.positions[symbol]
        side = SignalType.SELL if position_size > 0 else SignalType.BUY
        
        try:
            # Create a market order to close the position
            signal = Signal(
                type=side,
                strength=1.0,
                price=0.0,  # Market order, price not used
                take_profit=0.0,
                stop_loss=0.0
            )
            
            order = await self.market_strategy.execute(signal, abs(position_size), {})
            
            if order:
                self.open_orders[order.order_id] = order
                self.logger.info(f"Closed position for {symbol}: {position_size}")
                return True
            else:
                self.logger.error(f"Failed to close position for {symbol}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error closing position for {symbol}: {e}")
            return False
    
    async def update_portfolio_value(self, new_value: float):
        """Update the portfolio value"""
        old_value = self.portfolio_value
        self.portfolio_value = new_value
        
        # Calculate daily PnL
        daily_pnl = new_value - old_value
        self.daily_pnl += daily_pnl
        
        # Check circuit breaker conditions
        if self.daily_pnl < -self.portfolio_value * self.circuit_breaker_drawdown:
            self.logger.warning(f"Circuit breaker triggered: Daily drawdown exceeds {self.circuit_breaker_drawdown * 100}%")
            self.trading_enabled = False
        
        # Log the update
        self.logger.info(f"Portfolio value updated: {old_value:.2f} -> {new_value:.2f} (Daily PnL: {self.daily_pnl:.2f})")
    
    def _check_risk_parameters(self, signal: Signal) -> bool:
        """
        Check if a trade meets risk parameters.
        
        Args:
            signal: Trading signal to check
            
        Returns:
            True if trade meets risk parameters, False otherwise
        """
        # Check if we have an existing position
        current_position = self.positions.get("HYPE/USDC", 0.0)
        
        # Don't take opposing signals if we already have a position
        if (current_position > 0 and signal.type.value == "sell") or \
           (current_position < 0 and signal.type.value == "buy"):
            self.logger.info(f"Ignoring {signal.type.value} signal as it opposes current position")
            return False
        
        # Check maximum position size
        max_position_value = self.portfolio_value * self.max_position_size
        potential_position_value = abs(current_position) * signal.price
        
        if potential_position_value > max_position_value:
            self.logger.warning(f"Position size would exceed maximum ({potential_position_value:.2f} > {max_position_value:.2f})")
            return False
        

        return True
    
    def _determine_execution_strategy(self, signal: Signal, size: float, order_book: Dict[str, Any]) -> OrderType:
        """Determine the best execution strategy based on order size and liquidity"""
        # Use adaptive execution strategy if available
        if hasattr(self, 'adaptive_strategy'):
            self.logger.info("Using adaptive execution strategy")
            return self.adaptive_strategy.determine_execution_method(
                signal, size, order_book, self.portfolio_value
            )
            
        # Fallback to simple heuristic
        self.logger.info("Using simple execution strategy heuristic")
        
        # For large orders, use TWAP
        avg_volume = 1000.0  # Placeholder, should be calculated from historical data
        if size > avg_volume * self.twap_volume_threshold:
            return OrderType.TWAP
            
        # For medium orders, use iceberg
        if size > self.portfolio_value * self.iceberg_size_threshold:
            return OrderType.ICEBERG
            
        # For small orders, use limit
        return OrderType.LIMIT
