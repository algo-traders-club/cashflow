"""
Order models and management for the Cashflow trading system.

This module defines the Order class and related enums for order types and statuses.
"""
import time
from enum import Enum
from typing import Dict, Optional
from ..strategy import SignalType

class OrderType(Enum):
    """Types of orders"""
    LIMIT = "limit"
    MARKET = "market"
    TWAP = "twap"
    ICEBERG = "iceberg"

class OrderStatus(Enum):
    """Order statuses"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

class Order:
    """Represents an order in the trading system"""
    def __init__(
        self,
        order_id: str,
        symbol: str,
        side: SignalType,
        size: float,
        price: float,
        order_type: OrderType,
        time_in_force: str = "GTC",
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        metadata: Dict = None
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.size = size
        self.price = price
        self.order_type = order_type
        self.time_in_force = time_in_force
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.metadata = metadata or {}
        
        self.status = OrderStatus.PENDING
        self.filled_size = 0.0
        self.average_fill_price = 0.0
        self.created_at = time.time()
        self.updated_at = time.time()
        
    def __str__(self) -> str:
        return (f"Order({self.order_id}, {self.symbol}, {self.side.value}, "
                f"{self.size}, {self.price}, {self.status.value})")
                
    def update_status(self, status: OrderStatus):
        """Update order status and timestamp"""
        self.status = status
        self.updated_at = time.time()
        
    def update_fill(self, filled_size: float, average_fill_price: float):
        """Update fill information"""
        self.filled_size = filled_size
        self.average_fill_price = average_fill_price
        
        # Update status based on fill
        if filled_size >= self.size:
            self.status = OrderStatus.FILLED
        elif filled_size > 0:
            self.status = OrderStatus.PARTIALLY_FILLED
            
        self.updated_at = time.time()
        
    @property
    def is_active(self) -> bool:
        """Check if order is still active"""
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]
        
    @property
    def is_complete(self) -> bool:
        """Check if order is complete (filled or cancelled)"""
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]
