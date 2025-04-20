"""
Signal models for the Cashflow trading system.

This module defines the Signal class and related enums for trading signals.
"""
import pandas as pd
from enum import Enum
from typing import Dict, Optional

class SignalType(Enum):
    """Types of trading signals"""
    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"

class Signal:
    """Trading signal with metadata"""
    def __init__(
        self, 
        type: SignalType, 
        strength: float, 
        price: float, 
        take_profit: float, 
        stop_loss: float,
        metadata: Dict = None
    ):
        self.type = type
        self.strength = strength  # 0.0 to 1.0
        self.price = price
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.metadata = metadata or {}
        self.timestamp = pd.Timestamp.now()
    
    def __str__(self) -> str:
        return f"Signal({self.type.value}, strength={self.strength:.2f}, price={self.price:.4f})"
    
    def to_dict(self) -> Dict:
        """Convert signal to dictionary for serialization"""
        return {
            "type": self.type.value,
            "strength": self.strength,
            "price": self.price,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Signal':
        """Create signal from dictionary"""
        signal_type = SignalType(data["type"])
        
        return cls(
            type=signal_type,
            strength=data["strength"],
            price=data["price"],
            take_profit=data["take_profit"],
            stop_loss=data["stop_loss"],
            metadata=data.get("metadata", {})
        )
