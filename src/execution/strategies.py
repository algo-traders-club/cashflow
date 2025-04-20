"""
Execution strategies for the Cashflow trading system.

This module implements various order execution strategies including
TWAP, VWAP, and iceberg orders for minimizing market impact.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from .orders import Order, OrderType
from ..strategy import Signal

class ExecutionStrategy:
    """Base class for execution strategies"""
    
    def __init__(self, exchange_client):
        self.exchange = exchange_client
        self.logger = logging.getLogger("execution.strategies")
    
    async def execute(self, signal: Signal, size: float, order_book: Dict[str, Any]) -> Optional[Order]:
        """
        Execute the strategy.
        
        Args:
            signal: Trading signal
            size: Order size
            order_book: Current order book state
            
        Returns:
            Order object if order was placed, None otherwise
        """
        raise NotImplementedError("Subclasses must implement execute()")

class MarketOrderStrategy(ExecutionStrategy):
    """Simple market order execution strategy"""
    
    async def execute(self, signal: Signal, size: float, order_book: Dict[str, Any]) -> Optional[Order]:
        """Execute a market order"""
        try:
            # Create market order for spot trading
            is_buy = signal.type.value == "buy"
            result = self.exchange.order(
                coin="HYPE/USDC",  # Correct spot trading pair format
                is_buy=is_buy,
                sz=size,
                limit_px=0,  # Market order
                order_type={"market": {}}
            )
            
            if not result or "error" in result:
                self.logger.error(f"Market order failed: {result}")
                return None
            
            from .orders import Order, OrderType
            
            order_id = result.get("order_id")
            
            # Create Order object
            order = Order(
                order_id=order_id,
                symbol="HYPE/USDC",  # Correct spot trading pair format
                side=signal.type,
                size=size,
                price=signal.price,
                order_type=OrderType.MARKET,
                take_profit=signal.take_profit,
                stop_loss=signal.stop_loss
            )
            
            self.logger.info(f"Placed market order: {order}")
            return order
            
        except Exception as e:
            self.logger.error(f"Error executing market order: {e}")
            return None

class LimitOrderStrategy(ExecutionStrategy):
    """Limit order execution strategy with intelligent price placement"""
    
    async def execute(self, signal: Signal, size: float, order_book: Dict[str, Any]) -> Optional[Order]:
        """Execute a limit order with intelligent price placement"""
        try:
            # Determine optimal limit price based on order book
            limit_price = self._calculate_optimal_limit_price(signal, order_book)
            
            # Create limit order for spot trading
            is_buy = signal.type.value == "buy"
            result = self.exchange.order(
                coin="HYPE/USDC",  # Correct spot trading pair format
                is_buy=is_buy,
                sz=size,
                limit_px=limit_price,
                order_type={"limit": {"tif": "Gtc"}}
            )
            
            if not result or "error" in result:
                self.logger.error(f"Limit order failed: {result}")
                return None
            
            from .orders import Order, OrderType
            
            order_id = result.get("order_id")
            
            # Create Order object
            order = Order(
                order_id=order_id,
                symbol="USDC/HYPE",
                side=signal.type,
                size=size,
                price=limit_price,
                order_type=OrderType.LIMIT,
                time_in_force="GTC",
                take_profit=signal.take_profit,
                stop_loss=signal.stop_loss
            )
            
            self.logger.info(f"Placed limit order: {order}")
            return order
            
        except Exception as e:
            self.logger.error(f"Error executing limit order: {e}")
            return None
    
    def _calculate_optimal_limit_price(self, signal: Signal, order_book: Dict[str, Any]) -> float:
        """
        Calculate the optimal limit price based on the order book.
        
        Args:
            signal: Trading signal
            order_book: Current order book state
            
        Returns:
            Optimal limit price
        """
        # Extract bids and asks from order book
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        
        if not bids or not asks:
            return signal.price
        
        # Get best bid and ask
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else float('inf')
        
        # Calculate spread
        spread = best_ask - best_bid
        
        # For buy orders, place at best bid + 20% of spread
        if signal.type.value == "buy":
            return best_bid + (spread * 0.2)
        
        # For sell orders, place at best ask - 20% of spread
        else:
            return best_ask - (spread * 0.2)

class TWAPStrategy(ExecutionStrategy):
    """Time-Weighted Average Price execution strategy"""
    
    async def execute(self, signal: Signal, size: float, order_book: Dict[str, Any]) -> Optional[Order]:
        """Execute a TWAP order (Time-Weighted Average Price)"""
        try:
            # Split the order into smaller chunks
            chunk_count = 5
            chunk_size = size / chunk_count
            
            # Create a limit order strategy for placing chunks
            limit_strategy = LimitOrderStrategy(self.exchange)
            
            # Place the first chunk as a limit order
            first_order = await limit_strategy.execute(signal, chunk_size, order_book)
            
            if not first_order:
                return None
            
            # Store TWAP metadata
            first_order.metadata["twap_total_size"] = size
            first_order.metadata["twap_chunk_size"] = chunk_size
            first_order.metadata["twap_chunks_remaining"] = chunk_count - 1
            first_order.metadata["twap_interval"] = 60  # seconds
            
            # Schedule the remaining chunks
            asyncio.create_task(self._execute_remaining_chunks(
                signal, chunk_size, chunk_count - 1, order_book, limit_strategy
            ))
            
            return first_order
            
        except Exception as e:
            self.logger.error(f"Error executing TWAP order: {e}")
            return None
    
    async def _execute_remaining_chunks(self, signal: Signal, chunk_size: float, 
                                      remaining_chunks: int, order_book: Dict[str, Any],
                                      limit_strategy: LimitOrderStrategy):
        """Execute remaining chunks of a TWAP order"""
        # Wait between chunks
        chunk_interval = 60  # 1 minute between chunks
        
        for i in range(remaining_chunks):
            await asyncio.sleep(chunk_interval)
            
            # Get updated order book
            # In a real implementation, you would fetch the latest order book
            
            # Place the next chunk
            await limit_strategy.execute(signal, chunk_size, order_book)

class IcebergStrategy(ExecutionStrategy):
    """Iceberg order execution strategy"""
    
    async def execute(self, signal: Signal, size: float, order_book: Dict[str, Any]) -> Optional[Order]:
        """Execute an iceberg order (showing only a small portion of the total size)"""
        try:
            # Determine visible portion (10% of total size)
            visible_size = size * 0.1
            hidden_size = size - visible_size
            
            # Create a limit order strategy for placing the visible portion
            limit_strategy = LimitOrderStrategy(self.exchange)
            
            # Place the visible portion as a limit order
            visible_order = await limit_strategy.execute(signal, visible_size, order_book)
            
            if not visible_order:
                return None
            
            # Store the hidden size in the order metadata
            visible_order.metadata["hidden_size"] = hidden_size
            visible_order.metadata["is_iceberg"] = True
            
            # Set up a task to monitor this order and place the hidden portion when filled
            asyncio.create_task(self._monitor_iceberg_order(
                visible_order, signal, order_book, limit_strategy
            ))
            
            return visible_order
            
        except Exception as e:
            self.logger.error(f"Error executing iceberg order: {e}")
            return None
    
    async def _monitor_iceberg_order(self, order: Order, signal: Signal, 
                                   order_book: Dict[str, Any],
                                   limit_strategy: LimitOrderStrategy):
        """Monitor an iceberg order and place the hidden portion when the visible portion is filled"""
        from .orders import OrderStatus
        
        while True:
            await asyncio.sleep(5)
            
            # Check if the order is still active
            if not order.is_active:
                # Order might have been cancelled
                break
                
            # Check if the order has been filled
            if order.status == OrderStatus.FILLED:
                # Place the next portion
                hidden_size = order.metadata.get("hidden_size", 0.0)
                
                if hidden_size > 0:
                    # Calculate new visible and hidden sizes
                    next_visible_size = min(hidden_size, order.size)
                    next_hidden_size = hidden_size - next_visible_size
                    
                    # Place the next visible portion
                    next_order = await limit_strategy.execute(signal, next_visible_size, order_book)
                    
                    if next_order:
                        # Update metadata
                        next_order.metadata["hidden_size"] = next_hidden_size
                        next_order.metadata["is_iceberg"] = True
                        
                        # Start monitoring the new order
                        asyncio.create_task(self._monitor_iceberg_order(
                            next_order, signal, order_book, limit_strategy
                        ))
                
                # Stop monitoring this order
                break
