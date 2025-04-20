"""
FastAPI endpoints for monitoring and controlling the Cashflow trading system.

This module provides a RESTful API for starting/stopping the trading system,
monitoring performance, and updating configuration parameters.
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Models for request/response validation
class TradeConfig(BaseModel):
    """Model for strategy configuration parameters"""
    rsi_threshold_buy: float = Field(30, ge=0, le=100, description="RSI threshold for buy signals")
    rsi_threshold_sell: float = Field(70, ge=0, le=100, description="RSI threshold for sell signals")
    bb_period: int = Field(20, ge=5, le=50, description="Bollinger Bands period")
    bb_std_dev: float = Field(1.5, ge=0.5, le=3.0, description="Bollinger Bands standard deviation")
    ema_period: int = Field(50, ge=10, le=200, description="EMA period for trend confirmation")
    atr_period: int = Field(14, ge=5, le=30, description="ATR period")
    take_profit_atr_multiple: float = Field(1.5, ge=0.5, le=5.0, description="Take profit as multiple of ATR")
    stop_loss_atr_multiple: float = Field(0.5, ge=0.1, le=2.0, description="Stop loss as multiple of ATR")
    adx_threshold: float = Field(25, ge=10, le=50, description="ADX threshold for trend strength")

class RiskConfig(BaseModel):
    """Model for risk management configuration"""
    max_position_size: float = Field(0.1, ge=0.01, le=1.0, description="Maximum position size as fraction of portfolio")
    max_trade_risk: float = Field(0.01, ge=0.001, le=0.05, description="Maximum risk per trade as fraction of portfolio")
    circuit_breaker_drawdown: float = Field(0.05, ge=0.01, le=0.2, description="Daily drawdown to trigger circuit breaker")
    circuit_breaker_consecutive_losses: int = Field(3, ge=1, le=10, description="Consecutive losses to trigger circuit breaker")

class TradeStatus(BaseModel):
    """Model for trade status response"""
    id: str
    symbol: str
    side: str
    size: float
    price: float
    status: str
    filled_size: float
    average_fill_price: float
    created_at: datetime
    updated_at: datetime

class PortfolioStatus(BaseModel):
    """Model for portfolio status response"""
    portfolio_value: float
    positions: Dict[str, float]
    daily_pnl: float
    daily_pnl_percent: float
    trading_enabled: bool

class SystemStatus(BaseModel):
    """Model for system status response"""
    status: str
    uptime_seconds: int
    trades_today: int
    win_rate: float
    last_signal: Optional[Dict[str, Any]] = None

# JWT Authentication
class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
        self.secret_key = os.getenv("JWT_SECRET_KEY", "default_secret_key")
        
    async def __call__(self, request: Request) -> Dict[str, Any]:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authentication credentials"
            )
            
        if credentials.scheme != "Bearer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authentication scheme"
            )
            
        try:
            payload = jwt.decode(
                credentials.credentials,
                self.secret_key,
                algorithms=["HS256"]
            )
            return payload
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token or expired token"
            )

# API Application
class CashflowAPI:
    """FastAPI application for the Cashflow trading system"""
    
    def __init__(self):
        self.app = FastAPI(
            title="Cashflow Trading API",
            description="API for monitoring and controlling the Cashflow trading system",
            version="0.1.0"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Authentication
        self.security = JWTBearer()
        
        # Register routes
        self._register_routes()
        
        # Trading system reference (will be set by main.py)
        self.trading_system = None
        
        # Start time for uptime calculation
        self.start_time = datetime.now()
        
        self.logger = logging.getLogger("api")
    
    def _register_routes(self):
        """Register API routes"""
        
        @self.app.get("/", tags=["General"])
        async def root():
            """API root endpoint"""
            return {
                "name": "Cashflow Trading API",
                "version": "0.1.0",
                "status": "running"
            }
        
        @self.app.get("/status", response_model=SystemStatus, tags=["Monitoring"])
        async def get_status():
            """Get the current system status"""
            if not self.trading_system:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Trading system not initialized"
                )
                
            uptime = (datetime.now() - self.start_time).total_seconds()
            
            return {
                "status": "active" if self.trading_system.is_running else "inactive",
                "uptime_seconds": int(uptime),
                "trades_today": self.trading_system.trades_today,
                "win_rate": self.trading_system.win_rate,
                "last_signal": self.trading_system.last_signal
            }
        
        @self.app.get("/portfolio", response_model=PortfolioStatus, tags=["Monitoring"])
        async def get_portfolio():
            """Get the current portfolio status"""
            if not self.trading_system:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Trading system not initialized"
                )
                
            portfolio_value = self.trading_system.execution_engine.portfolio_value
            daily_pnl = self.trading_system.execution_engine.daily_pnl
            daily_pnl_percent = (daily_pnl / portfolio_value) * 100 if portfolio_value > 0 else 0
                
            return {
                "portfolio_value": portfolio_value,
                "positions": self.trading_system.execution_engine.positions,
                "daily_pnl": daily_pnl,
                "daily_pnl_percent": daily_pnl_percent,
                "trading_enabled": self.trading_system.execution_engine.trading_enabled
            }
        
        @self.app.get("/trades", response_model=List[TradeStatus], tags=["Monitoring"])
        async def get_trades(limit: int = 10):
            """Get recent trades"""
            if not self.trading_system:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Trading system not initialized"
                )
                
            # Convert internal orders to TradeStatus model
            trades = []
            for order_id, order in self.trading_system.execution_engine.open_orders.items():
                trades.append({
                    "id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "size": order.size,
                    "price": order.price,
                    "status": order.status,
                    "filled_size": order.filled_size,
                    "average_fill_price": order.average_fill_price,
                    "created_at": order.created_at,
                    "updated_at": order.updated_at
                })
            
            return trades[:limit]
        
        @self.app.get("/debug", tags=["Diagnostics"])
        async def get_debug_info():
            """Get debug information about the trading system"""
            if not self.trading_system:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Trading system not initialized"
                )
                
            # Collect debug information
            strategy = self.trading_system.strategy
            risk_manager = self.trading_system.execution_engine.risk_manager
            data_manager = self.trading_system.data_manager
            
            # Get latest market data
            latest_1m = None
            latest_5m = None
            try:
                df_1m = data_manager.get_candles('1m')
                df_5m = data_manager.get_candles('5m')
                if not df_1m.empty:
                    latest_1m = df_1m.iloc[-1].to_dict()
                if not df_5m.empty:
                    latest_5m = df_5m.iloc[-1].to_dict()
            except Exception as e:
                latest_1m = {"error": str(e)}
                latest_5m = {"error": str(e)}
            
            # Get strategy parameters
            strategy_params = {
                "rsi_oversold": strategy.rsi_oversold,
                "rsi_overbought": strategy.rsi_overbought,
                "bb_std_dev": strategy.bb_std_dev,
                "volume_threshold": getattr(strategy, 'volume_threshold', None),
                "signal_boost": "20% (aggressive mode)"
            }
            
            # Get risk parameters
            risk_params = {
                "max_position_size": risk_manager.max_position_size,
                "max_trade_risk": risk_manager.max_trade_risk,
                "circuit_breaker_drawdown": risk_manager.base_drawdown_threshold if hasattr(risk_manager, 'base_drawdown_threshold') else risk_manager.circuit_breaker_drawdown,
                "volatility_ceiling": getattr(risk_manager, 'volatility_ceiling', None)
            }
            
            # Get order book snapshot
            order_book = data_manager.get_current_orderbook()
            
            return {
                "strategy_type": strategy.__class__.__name__,
                "risk_manager_type": risk_manager.__class__.__name__,
                "latest_1m_candle": latest_1m,
                "latest_5m_candle": latest_5m,
                "strategy_parameters": strategy_params,
                "risk_parameters": risk_params,
                "order_book_snapshot": order_book,
                "trading_enabled": self.trading_system.execution_engine.trading_enabled,
                "aggressive_mode": True,
                "portfolio_value": self.trading_system.execution_engine.portfolio_value
            }
        
        @self.app.post("/start", tags=["Control"])
        async def start_trading():
            """Start the trading system"""
            if not self.trading_system:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Trading system not initialized"
                )
                
            if self.trading_system.is_running:
                return {"status": "already_running"}
                
            await self.trading_system.start()
            return {"status": "started"}
        
        @self.app.post("/stop", tags=["Control"])
        async def stop_trading():
            """Stop the trading system"""
            if not self.trading_system:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Trading system not initialized"
                )
                
            if not self.trading_system.is_running:
                return {"status": "already_stopped"}
                
            await self.trading_system.stop()
            return {"status": "stopped"}
        
        @self.app.post("/config/strategy", tags=["Configuration"])
        async def update_strategy_config(config: TradeConfig):
            """Update strategy configuration parameters"""
            if not self.trading_system:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Trading system not initialized"
                )
                
            # Update strategy configuration
            self.trading_system.update_strategy_config(config.dict())
            return {"status": "configuration_updated"}
        
        @self.app.post("/config/risk", tags=["Configuration"])
        async def update_risk_config(config: RiskConfig):
            """Update risk management configuration"""
            if not self.trading_system:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Trading system not initialized"
                )
                
            # Update risk configuration
            self.trading_system.update_risk_config(config.dict())
            return {"status": "configuration_updated"}
        
        @self.app.post("/reset", tags=["Control"])
        async def reset_circuit_breaker():
            """Reset circuit breaker and re-enable trading"""
            if not self.trading_system:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Trading system not initialized"
                )
                
            self.trading_system.execution_engine.trading_enabled = True
            self.trading_system.execution_engine.consecutive_losses = 0
            self.trading_system.execution_engine.daily_pnl = 0.0
            
            return {"status": "circuit_breaker_reset"}
    
    def run(self, host: str = "0.0.0.0", port: int = 8000, max_attempts: int = 10):
        """Run the API server with port fallback"""
        for attempt in range(max_attempts):
            try:
                # Try to run on the current port
                self.logger.info(f"Attempting to start API server on port {port}")
                uvicorn.run(self.app, host=host, port=port)
                break
            except OSError as e:
                if "address already in use" in str(e).lower() and attempt < max_attempts - 1:
                    port += 1
                    self.logger.info(f"Port {port-1} is in use, trying port {port}")
                else:
                    self.logger.error(f"Failed to start API server: {e}")
                    raise
    
    def set_trading_system(self, trading_system):
        """Set the trading system reference"""
        self.trading_system = trading_system
        self.logger.info("Trading system reference set")
