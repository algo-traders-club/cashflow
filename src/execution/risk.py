"""
Risk management and order sizing for the Cashflow trading system.

This module handles risk-based order sizing and liquidity analysis.
"""
import logging
from typing import Dict, Any, Optional
import asyncio
import time
from ..strategy import Signal

class RiskManager:
    """
    Handles risk management and order sizing based on portfolio value,
    signal strength, and market liquidity.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the risk manager.
        
        Args:
            config: Risk configuration parameters
        """
        # Risk parameters
        self.max_position_size = config.get("max_position_size", 0.1)  # 10% of portfolio
        self.max_trade_risk = config.get("max_trade_risk", 0.01)  # 1% per trade
        
        self.logger = logging.getLogger("execution.risk")
    
    def calculate_order_size(self, signal: Signal, order_book: Dict[str, Any], 
                           portfolio_value: float, current_position: float) -> float:
        """
        Calculate order size based on signal strength and liquidity.
        
        Args:
            signal: Trading signal
            order_book: Current order book state
            portfolio_value: Current portfolio value
            current_position: Current position size
            
        Returns:
            Order size
        """
        # Base size calculation using portfolio value and signal strength
        base_size = portfolio_value * self.max_trade_risk * signal.strength
        
        # Adjust based on risk (stop loss distance)
        stop_distance = abs(signal.price - signal.stop_loss)
        if stop_distance > 0:
            risk_adjusted_size = (portfolio_value * self.max_trade_risk) / stop_distance
            base_size = min(base_size, risk_adjusted_size)
        
        # Adjust based on order book liquidity
        liquidity_adjusted_size = self._adjust_size_for_liquidity(base_size, signal, order_book)
        
        # Ensure we don't exceed maximum position size
        max_position_size = portfolio_value * self.max_position_size / signal.price
        available_position_size = max_position_size - abs(current_position)
        
        final_size = min(liquidity_adjusted_size, available_position_size)
        
        self.logger.info(f"Calculated order size: {final_size} (base: {base_size}, liquidity adjusted: {liquidity_adjusted_size})")
        return final_size
    
    def _adjust_size_for_liquidity(self, base_size: float, signal: Signal, order_book: Dict[str, Any]) -> float:
        """
        Adjust order size based on order book liquidity.
        
        Args:
            base_size: Base order size
            signal: Trading signal
            order_book: Current order book state
            
        Returns:
            Liquidity-adjusted order size
        """
        # This is a simplified implementation
        # In production, you would analyze the order book depth more thoroughly
        
        # Extract bids and asks from order book
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        
        # Determine which side of the book to analyze based on signal type
        relevant_side = asks if signal.type.value == "buy" else bids
        
        # Calculate available liquidity within 0.5% of current price
        price_threshold = signal.price * 0.005  # 0.5%
        available_liquidity = 0.0
        
        for level in relevant_side:
            price = level[0]
            size = level[1]
            
            # Check if price is within threshold
            if abs(price - signal.price) <= price_threshold:
                available_liquidity += size
        
        # If available liquidity is less than 2x our base size, reduce size
        if available_liquidity < base_size * 2:
            adjusted_size = base_size * (available_liquidity / (base_size * 2))
            self.logger.warning(f"Reducing order size due to limited liquidity: {base_size} -> {adjusted_size}")
            return adjusted_size
        
        return base_size

class OrderMonitor:
    """
    Monitors open orders and handles order status updates.
    """
    
    def __init__(self, exchange, open_orders, stale_order_timeout=300):
        """
        Initialize the order monitor.
        
        Args:
            exchange: Exchange client
            open_orders: Dictionary of open orders
            stale_order_timeout: Timeout for stale orders in seconds
        """
        self.exchange = exchange
        self.open_orders = open_orders
        self.stale_order_timeout = stale_order_timeout
        self.logger = logging.getLogger("execution.monitor")
    
    async def monitor_orders(self):
        """Monitor open orders and handle stale orders"""
        while True:
            try:
                current_time = time.time()
                
                # Check for stale orders
                stale_orders = []
                for order_id, order in self.open_orders.items():
                    if (order.status.value == "open" and 
                        current_time - order.updated_at > self.stale_order_timeout):
                        stale_orders.append(order_id)
                
                # Cancel stale orders
                for order_id in stale_orders:
                    self.logger.warning(f"Cancelling stale order {order_id}")
                    try:
                        result = self.exchange.cancel("USDC/HYPE", [order_id])
                        
                        if result and "success" in result and result["success"]:
                            from .orders import OrderStatus
                            self.open_orders[order_id].status = OrderStatus.CANCELLED
                            self.open_orders[order_id].updated_at = time.time()
                    except Exception as e:
                        self.logger.error(f"Error cancelling stale order {order_id}: {e}")
                
                # Update order statuses
                await self.update_order_statuses()
                
                # Sleep for a bit
                await asyncio.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Error in order monitor: {e}")
                await asyncio.sleep(30)  # Longer sleep on error
    
    async def update_order_statuses(self):
        """Update the status of all open orders"""
        if not self.open_orders:
            return
            
        try:
            # Get all open orders from the exchange
            exchange_orders = self.exchange.get_open_orders("USDC/HYPE")
            
            # Create a map of exchange order IDs
            exchange_order_map = {order["id"]: order for order in exchange_orders}
            
            # Update local order statuses
            for order_id, order in list(self.open_orders.items()):
                if not order.is_active:
                    continue
                    
                if order_id in exchange_order_map:
                    # Order is still open, update any changed fields
                    exchange_order = exchange_order_map[order_id]
                    order.filled_size = exchange_order.get("filled_size", 0.0)
                    
                    if order.filled_size > 0 and order.filled_size < order.size:
                        from .orders import OrderStatus
                        order.status = OrderStatus.PARTIALLY_FILLED
                    
                    # Update average fill price if available
                    if "average_fill_price" in exchange_order:
                        order.average_fill_price = exchange_order["average_fill_price"]
                        
                else:
                    # Order not in exchange open orders, check if it was filled
                    order_history = self.exchange.get_order_history("USDC/HYPE", [order_id])
                    
                    if order_history and order_id in order_history:
                        history_order = order_history[order_id]
                        
                        if history_order.get("status") == "filled":
                            from .orders import OrderStatus
                            order.status = OrderStatus.FILLED
                            order.filled_size = order.size
                            order.average_fill_price = history_order.get("average_fill_price", order.price)
                            
                        elif history_order.get("status") == "cancelled":
                            from .orders import OrderStatus
                            order.status = OrderStatus.CANCELLED
                            
                        elif history_order.get("status") == "rejected":
                            from .orders import OrderStatus
                            order.status = OrderStatus.REJECTED
                            
                        elif history_order.get("status") == "expired":
                            from .orders import OrderStatus
                            order.status = OrderStatus.EXPIRED
                
                order.updated_at = time.time()
                
        except Exception as e:
            self.logger.error(f"Error updating order statuses: {e}")
