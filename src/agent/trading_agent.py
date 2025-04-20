"""
Core trading agent for Cashflow trading system.

This module implements the main trading agent that coordinates data, strategy,
and execution components.
"""
import asyncio
import logging
import time
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import yaml

from ..data import DataManager
from ..strategy import HybridStrategy, Signal
from ..strategy.enhanced_strategy import EnhancedHybridStrategy
from ..execution import ExecutionEngine
from ..execution.enhanced_risk import EnhancedRiskManager
from ..execution.adaptive_strategy import AdaptiveExecutionStrategy
from ..utils.metrics import EnhancedMetricsCollector
from .trading_loop import TradingLoop

class TradingAgent:
    """
    Main trading agent that coordinates data, strategy, and execution.
    
    This class is responsible for:
    1. Initializing and coordinating all components
    2. Running the main trading loop
    3. Implementing risk management and circuit breakers
    4. Tracking performance metrics
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the trading agent.
        
        Args:
            config_path: Path to the configuration file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Set up logging
        self._setup_logging()
        self.logger = logging.getLogger("agent")
        
        # Initialize components
        self.data_manager = DataManager(
            db_path=self.config.get("data", {}).get("db_path", "data/market_data.db")
        )
        
        # Use enhanced strategy if enabled in config
        use_enhanced_strategy = self.config.get("strategy", {}).get("use_enhanced_strategy", True)
        if use_enhanced_strategy:
            self.logger.info("Using EnhancedHybridStrategy")
            self.strategy = EnhancedHybridStrategy(
                config=self.config.get("strategy", {})
            )
        else:
            self.strategy = HybridStrategy(
                config=self.config.get("strategy", {})
            )
        
        # Initialize execution engine
        self.execution_engine = ExecutionEngine(
            private_key=os.getenv("PRIVATE_KEY"),
            config=self.config.get("execution", {})
        )
        
        # Initialize enhanced risk manager if enabled
        use_enhanced_risk = self.config.get("execution", {}).get("use_enhanced_risk", True)
        if use_enhanced_risk:
            self.logger.info("Using EnhancedRiskManager")
            self.execution_engine.risk_manager = EnhancedRiskManager(
                self.config.get("execution", {})
            )
            
        # Initialize adaptive execution strategy if enabled
        use_adaptive_execution = self.config.get("execution", {}).get("adaptive_execution", True)
        if use_adaptive_execution:
            self.logger.info("Using AdaptiveExecutionStrategy")
            self.execution_engine.adaptive_strategy = AdaptiveExecutionStrategy(
                self.execution_engine.exchange,
                self.config.get("execution", {})
            )
            
        # Initialize metrics collector
        metrics_enabled = self.config.get("metrics", {}).get("enabled", True)
        if metrics_enabled:
            self.logger.info("Initializing EnhancedMetricsCollector")
            self.metrics_collector = EnhancedMetricsCollector()
        else:
            self.metrics_collector = None
        
        # Create trading loop
        self.trading_loop = TradingLoop(
            self.data_manager,
            self.strategy,
            self.execution_engine,
            self.config.get("agent", {}).get("check_interval", 60),
            metrics_collector=self.metrics_collector if hasattr(self, 'metrics_collector') else None
        )
        
        # Tasks
        self._main_task = None
        self.is_running = False
        
        self.logger.info("TradingAgent initialized")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            # Default configuration if file can't be loaded
            print(f"Error loading configuration: {e}")
            return {
                "agent": {
                    "check_interval": 60,
                    "log_level": "INFO"
                },
                "data": {
                    "db_path": "data/market_data.db"
                },
                "strategy": {
                    "bb_period": 20,
                    "bb_std_dev": 1.5,
                    "rsi_period": 14,
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                    "ema_period": 50,
                    "adx_period": 14,
                    "adx_threshold": 25,
                    "atr_period": 14,
                    "take_profit_atr_multiple": 1.5,
                    "stop_loss_atr_multiple": 0.5
                },
                "execution": {
                    "max_position_size": 0.1,
                    "max_trade_risk": 0.01,
                    "circuit_breaker_drawdown": 0.05,
                    "circuit_breaker_consecutive_losses": 3,
                    "twap_volume_threshold": 0.005,
                    "iceberg_size_threshold": 0.01,
                    "stale_order_timeout": 300,
                    "initial_portfolio_value": 1000.0
                }
            }
    
    def _setup_logging(self):
        """Set up logging configuration"""
        log_level = self.config.get("agent", {}).get("log_level", "INFO")
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Set up file handler
        file_handler = logging.FileHandler(f"logs/cashflow_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler.setFormatter(logging.Formatter(log_format))
        
        # Set up console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
    
    async def initialize(self):
        """Initialize all components"""
        self.logger.info("Initializing trading agent components")
        
        # Initialize data manager
        await self.data_manager.initialize()
        
        # Initialize execution engine
        await self.execution_engine.initialize()
        
        self.logger.info("All components initialized")
    
    async def start(self):
        """Start the trading agent"""
        if self.is_running:
            self.logger.warning("Trading agent is already running")
            return
        
        self.logger.info("Starting trading agent")
        self.is_running = True
        
        # Start the main trading loop
        self._main_task = asyncio.create_task(self.trading_loop.run())
        
        self.logger.info("Trading agent started")
    
    async def stop(self):
        """Stop the trading agent"""
        if not self.is_running:
            self.logger.warning("Trading agent is not running")
            return
        
        self.logger.info("Stopping trading agent")
        self.is_running = False
        
        # Stop the trading loop
        await self.trading_loop.stop()
        
        # Cancel the main task
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Trading agent stopped")
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate"""
        return self.trading_loop.win_rate
        
    @property
    def trades_today(self) -> int:
        """Get number of trades today"""
        return self.trading_loop.trades_today
        
    @property
    def last_signal(self) -> Dict:
        """Get the last generated signal"""
        return self.trading_loop.last_signal
    
    def update_strategy_config(self, config: Dict):
        """Update strategy configuration"""
        # Update internal config
        self.config["strategy"].update(config)
        
        # Create a new strategy instance with updated config
        self.strategy = HybridStrategy(config=self.config["strategy"])
        
        self.logger.info(f"Strategy configuration updated: {config}")
    
    def update_risk_config(self, config: Dict):
        """Update risk management configuration"""
        # Update internal config
        self.config["execution"].update(config)
        
        # Update execution engine config
        for key, value in config.items():
            setattr(self.execution_engine, key, value)
        
        self.logger.info(f"Risk configuration updated: {config}")
    
    def close(self):
        """Close all components"""
        self.logger.info("Closing trading agent")
        
        # Close data manager
        self.data_manager.close()
        
        # Close execution engine
        self.execution_engine.close()
        
        self.logger.info("Trading agent closed")
