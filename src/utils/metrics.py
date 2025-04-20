"""
Enhanced metrics collection for the Cashflow trading system.

This module provides comprehensive performance monitoring and metrics
collection for trading system optimization.
"""
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from prometheus_client import Counter, Gauge, Histogram, Summary

from ..execution.orders import Order, OrderType, OrderStatus

class EnhancedMetricsCollector:
    """
    Enhanced metrics collection for trading system performance monitoring.
    
    Features:
    - Order execution metrics (latency, slippage, fill ratio)
    - Strategy performance metrics (win rate, profit factor)
    - System health metrics (API latency, error rates)
    - Historical performance tracking
    """
    
    def __init__(self):
        """Initialize the metrics collector."""
        # Trading metrics
        self.trades_counter = Counter('cashflow_trades_total', 'Total number of trades', ['side', 'result'])
        self.trade_volume = Counter('cashflow_trade_volume_total', 'Total trading volume', ['side'])
        self.pnl_gauge = Gauge('cashflow_pnl_current', 'Current profit and loss')
        self.portfolio_value = Gauge('cashflow_portfolio_value', 'Current portfolio value')
        self.win_rate = Gauge('cashflow_win_rate', 'Current win rate')
        self.profit_factor = Gauge('cashflow_profit_factor', 'Current profit factor')
        
        # Order execution metrics
        self.order_latency = Histogram('cashflow_order_latency_seconds', 'Order execution latency',
                                     buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0])
        self.signal_latency = Histogram('cashflow_signal_latency_seconds', 'Signal generation latency',
                                      buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0])
        self.slippage = Histogram('cashflow_order_slippage_bps', 'Order slippage in basis points',
                                buckets=[1, 5, 10, 25, 50, 100, 250, 500])
        self.fill_ratio = Gauge('cashflow_order_fill_ratio', 'Order fill ratio')
        
        # System health metrics
        self.api_latency = Histogram('cashflow_api_latency_seconds', 'API request latency',
                                   buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0])
        self.error_counter = Counter('cashflow_errors_total', 'Total number of errors', ['component', 'type'])
        self.websocket_reconnects = Counter('cashflow_websocket_reconnects_total', 'WebSocket reconnection attempts')
        
        # Aggressive trading metrics
        self.aggression_ratio = Gauge('cashflow_aggression_ratio', 'Ratio of trades taken vs opportunities')
        self.position_size_distribution = Histogram('cashflow_position_size_distribution', 'Distribution of position sizes',
                                                 buckets=[0.01, 0.02, 0.03, 0.04, 0.05, 0.075, 0.1])
        self.risk_adjusted_return = Gauge('cashflow_risk_adjusted_return', 'Risk-adjusted return metrics')
        self.aggression_coefficient = Gauge('cashflow_aggression_coefficient', 'Actual vs max possible position sizing')
        self.signal_opportunities = Counter('cashflow_signal_opportunities_total', 'Total number of trading opportunities')
        self.signals_taken = Counter('cashflow_signals_taken_total', 'Total number of signals acted upon')
        
        # Historical trade data
        self.trade_history = []
        self.max_history_size = 1000  # Maximum number of trades to keep in memory
        
        self.logger = logging.getLogger("utils.metrics")
        
    def record_trade(self, order: Order, result: str, pnl: float):
        """
        Record a completed trade.
        
        Args:
            order: Completed order
            result: Trade result ('win', 'loss', 'breakeven')
            pnl: Profit and loss from the trade
        """
        self.record_trade_result(order, pnl, result)
        self.trade_volume.labels(side=order.side.value).inc(order.filled_size)
        
    def record_trade_result(self, order: Order, pnl: float, result: str):
        """Record trade result metrics."""
        self.trades_counter.labels(side=order.side.value, result=result).inc()
        
        # Update historical trade data
        trade_data = {
            'timestamp': datetime.now(),
            'symbol': order.symbol,
            'side': order.side.value,
            'size': order.size,
            'entry_price': order.average_fill_price,
            'exit_price': order.exit_price,
            'pnl': pnl,
            'result': result
        }
        
        self.trade_history.append(trade_data)
        # Trim history if needed
        if len(self.trade_history) > self.max_history_size:
            self.trade_history = self.trade_history[-self.max_history_size:]
        
        # Calculate and update win rate and profit factor
        self._update_performance_metrics()
        
        # Update aggressive trading metrics
        self.signals_taken.inc()
        self.position_size_distribution.observe(order.size)
        self._update_aggression_metrics()
        
        self.logger.info(f"Trade recorded: {order.side.value} {order.filled_size} @ {order.average_fill_price:.4f}, "
                       f"result={result}, pnl={pnl:.4f}")
        

        
    def record_order_execution(self, order: Order, executed_price: float, expected_price: float = None):
        """
        Record order execution metrics.
        
        Args:
            order: Executed order
            executed_price: Actual execution price
            expected_price: Expected execution price (optional)
        """
        # Calculate execution latency
        if order.created_at and order.updated_at:
            latency = order.updated_at - order.created_at
            self.order_latency.observe(latency)
            
        # Calculate slippage if expected price is provided
        if expected_price and expected_price > 0:
            slippage_pct = (executed_price - expected_price) / expected_price
            # Convert to basis points and adjust sign for buy/sell
            if order.side.value == "buy":
                slippage_bps = slippage_pct * 10000  # Higher execution price = positive slippage (bad)
            else:
                slippage_bps = -slippage_pct * 10000  # Lower execution price = positive slippage (bad)
                
            self.slippage.observe(abs(slippage_bps))
            
            self.logger.info(f"Order slippage: {slippage_bps:.2f} bps, "
                           f"expected={expected_price:.4f}, actual={executed_price:.4f}")
            
        # Record fill ratio for limit orders
        if order.order_type == OrderType.LIMIT:
            fill_ratio = order.filled_size / order.size if order.size > 0 else 0
            self.fill_ratio.set(fill_ratio)
            
            self.logger.info(f"Limit order fill ratio: {fill_ratio:.2%}, "
                           f"size={order.size}, filled={order.filled_size}")
            
    def record_signal_latency(self, latency_seconds: float):
        """
        Record signal generation latency.
        
        Args:
            latency_seconds: Signal generation latency in seconds
        """
        self.signal_latency.observe(latency_seconds)
        
    def record_api_request(self, endpoint: str, latency_seconds: float, success: bool):
        """
        Record API request metrics.
        
        Args:
            endpoint: API endpoint
            latency_seconds: Request latency in seconds
            success: Whether the request was successful
        """
        self.api_latency.observe(latency_seconds)
        
        if not success:
            self.error_counter.labels(component="api", type="request_error").inc()
            
    def record_error(self, component: str, error_type: str):
        """
        Record an error.
        
        Args:
            component: System component where the error occurred
            error_type: Type of error
        """
        self.error_counter.labels(component=component, type=error_type).inc()
        
    def record_websocket_reconnect(self):
        """Record a WebSocket reconnection attempt."""
        self.websocket_reconnects.inc()
        
    def update_portfolio_metrics(self, portfolio_value: float, daily_pnl: float):
        """
        Update portfolio metrics.
        
        Args:
            portfolio_value: Current portfolio value
            daily_pnl: Daily profit and loss
        """
        self.portfolio_value.set(portfolio_value)
        self.pnl_gauge.set(daily_pnl)
        
    def get_performance_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get performance summary for the specified time period.
        
        Args:
            days: Number of days to include in the summary
            
        Returns:
            Dictionary with performance metrics
        """
        # Filter trades by time period
        cutoff_time = datetime.now() - timedelta(days=days)
        recent_trades = [t for t in self.trade_history if t['timestamp'] >= cutoff_time]
        
        if not recent_trades:
            return {
                'trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'net_pnl': 0.0
            }
            
        # Calculate metrics
        wins = [t for t in recent_trades if t['result'] == 'win']
        losses = [t for t in recent_trades if t['result'] == 'loss']
        
        win_rate = len(wins) / len(recent_trades) if recent_trades else 0
        
        total_profit = sum(t['pnl'] for t in wins) if wins else 0
        total_loss = abs(sum(t['pnl'] for t in losses)) if losses else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        avg_win = total_profit / len(wins) if wins else 0
        avg_loss = total_loss / len(losses) if losses else 0
        
        largest_win = max([t['pnl'] for t in wins]) if wins else 0
        largest_loss = min([t['pnl'] for t in losses]) if losses else 0
        
        net_pnl = sum(t['pnl'] for t in recent_trades)
        
        return {
            'trades': len(recent_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'net_pnl': net_pnl
        }
        
    def _update_performance_metrics(self):
        """Update performance metrics based on trade history."""
        if not self.trade_history:
            return
            
        # Calculate win rate
        wins = sum(1 for trade in self.trade_history if trade['result'] == 'win')
        total_trades = len(self.trade_history)
        win_rate = wins / total_trades if total_trades > 0 else 0
        self.win_rate.set(win_rate)
        
        # Calculate profit factor
        gross_profits = sum(trade['pnl'] for trade in self.trade_history if trade['pnl'] > 0)
        gross_losses = abs(sum(trade['pnl'] for trade in self.trade_history if trade['pnl'] < 0))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')
        self.profit_factor.set(profit_factor if not np.isinf(profit_factor) else 0)
        
        # Calculate risk-adjusted return (Sharpe ratio-like metric)
        returns = [trade['pnl'] for trade in self.trade_history]
        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            risk_adjusted = mean_return / std_return if std_return > 0 else 0
            self.risk_adjusted_return.set(risk_adjusted)
            
    def _update_aggression_metrics(self):
        """Update aggressive trading metrics."""
        if not self.trade_history:
            return
            
        # Calculate aggression ratio
        signals_taken = self.signals_taken.get()
        signal_opportunities = self.signal_opportunities.get()
        aggression_ratio = signals_taken / signal_opportunities if signal_opportunities > 0 else 0
        self.aggression_ratio.set(aggression_ratio)
        
        # Calculate aggression coefficient
        position_sizes = [trade['size'] for trade in self.trade_history]
        max_position_size = max(position_sizes) if position_sizes else 0
        aggression_coefficient = max_position_size / 0.1 if max_position_size > 0 else 0
        self.aggression_coefficient.set(aggression_coefficient)
        
    def record_signal_opportunity(self, signal_type: str, signal_strength: float):
        """
        Record a trading signal opportunity, whether taken or not.
        
        Args:
            signal_type: Type of signal (buy/sell)
            signal_strength: Strength of the signal (0-1)
        """
        self.signal_opportunities.inc()
        self.logger.debug(f"Signal opportunity recorded: {signal_type}, strength={signal_strength:.2f}")
        self._update_aggression_metrics()
    
    def get_trade_history_dataframe(self) -> pd.DataFrame:
        """
        Get trade history as a pandas DataFrame.
        
        Returns:
            DataFrame containing trade history
        """
        return pd.DataFrame(self.trade_history)
