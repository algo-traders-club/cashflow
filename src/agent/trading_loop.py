"""
Trading loop implementation for the Cashflow trading system.

This module implements the main trading loop and signal processing logic.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional

class TradingLoop:
    """
    Implements the main trading loop for the Cashflow trading system.
    
    This class handles:
    1. Periodic checking for trading signals
    2. Executing signals through the execution engine
    3. Monitoring open positions for exit conditions
    """
    
    def __init__(self, data_manager, strategy, execution_engine, check_interval=60, metrics_collector=None):
        """
        Initialize the trading loop.
        
        Args:
            data_manager: Data manager instance
            strategy: Strategy instance
            execution_engine: Execution engine instance
            check_interval: Interval between checks in seconds
            metrics_collector: Optional metrics collector for performance tracking
        """
        self.data_manager = data_manager
        self.strategy = strategy
        self.execution_engine = execution_engine
        self.check_interval = check_interval
        self.metrics_collector = metrics_collector
        
        self.is_running = False
        self.last_check_time = time.time()
        self.trades_today = 0
        self.wins = 0
        self.losses = 0
        self.last_signal = None
        
        self.logger = logging.getLogger("agent.trading_loop")
    
    async def run(self):
        """Run the main trading loop"""
        self.logger.info("Trading loop started")
        self.is_running = True
        
        while self.is_running:
            try:
                # Check if it's time to run the strategy
                current_time = time.time()
                if current_time - self.last_check_time >= self.check_interval:
                    self.last_check_time = current_time
                    await self._check_for_signals()
                
                # Check for exit conditions on open positions
                await self._check_exit_conditions()
                
                # Sleep to avoid high CPU usage
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(10)  # Longer sleep on error
    
    async def stop(self):
        """Stop the trading loop"""
        self.logger.info("Stopping trading loop")
        self.is_running = False
    
    async def _check_for_signals(self):
        """Check for trading signals"""
        try:
            # Get latest data
            df_1m = self.data_manager.get_candles("1m", limit=100)
            df_5m = self.data_manager.get_candles("5m", limit=100)
            
            # Skip if we don't have enough data
            if df_1m.empty or df_5m.empty:
                self.logger.warning("Not enough data to generate signals")
                return
            
            # Calculate indicators
            df_1m, df_5m = self.strategy.calculate_indicators(df_1m, df_5m)
            
            # Generate signal
            signal = self.strategy.generate_signal(df_1m, df_5m)
            
            if signal:
                self.logger.info(f"Generated signal: {signal}")
                self.last_signal = signal.to_dict()
                
                # Measure signal generation latency if metrics collector is available
                signal_start_time = time.time()
                
                # Execute the signal
                order_book = self.data_manager.get_current_orderbook()
                order = await self.execution_engine.execute_signal(signal, order_book)
                
                if order:
                    self.logger.info(f"Executed signal: {order}")
                    self.trades_today += 1
                    
                    # Record metrics if available
                    if self.metrics_collector:
                        signal_latency = time.time() - signal_start_time
                        self.metrics_collector.record_signal_latency(signal_latency)
                        
                        # Record order execution metrics
                        self.metrics_collector.record_order_execution(
                            order, 
                            order.average_fill_price, 
                            signal.price
                        )
                else:
                    self.logger.warning("Failed to execute signal")
            
        except Exception as e:
            self.logger.error(f"Error checking for signals: {e}")
    
    async def _check_exit_conditions(self):
        """Check exit conditions for open positions"""
        try:
            # Get open orders
            open_orders = self.execution_engine.open_orders
            
            # Get latest price
            df_1m = self.data_manager.get_candles("1m", limit=1)
            if df_1m.empty:
                return
                
            # Use 'c' instead of 'close' for spot trading candle data according to Hyperliquid API docs
            current_price = df_1m.iloc[-1]["c"]
            
            # Check each open order for exit conditions
            for order_id, order in list(open_orders.items()):
                # Skip orders that aren't filled
                if order.status.value != "filled":
                    continue
                
                # Check take profit
                if order.take_profit:
                    if (order.side.value == "buy" and current_price >= order.take_profit) or \
                       (order.side.value == "sell" and current_price <= order.take_profit):
                        self.logger.info(f"Take profit reached for order {order_id}")
                        await self.execution_engine.close_position(order.symbol)
                        self.wins += 1
                        continue
                
                # Check stop loss
                if order.stop_loss:
                    if (order.side.value == "buy" and current_price <= order.stop_loss) or \
                       (order.side.value == "sell" and current_price >= order.stop_loss):
                        self.logger.info(f"Stop loss reached for order {order_id}")
                        await self.execution_engine.close_position(order.symbol)
                        self.losses += 1
                        continue
                
                # Check time-based exit (30 minutes)
                if time.time() - order.created_at > 1800:  # 30 minutes
                    self.logger.info(f"Time-based exit for order {order_id}")
                    await self.execution_engine.close_position(order.symbol)
                    
                    # Determine if win or loss
                    if (order.side.value == "buy" and current_price > order.price) or \
                       (order.side.value == "sell" and current_price < order.price):
                        self.wins += 1
                    else:
                        self.losses += 1
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate"""
        total_trades = self.wins + self.losses
        if total_trades == 0:
            return 0.0
        return self.wins / total_trades
