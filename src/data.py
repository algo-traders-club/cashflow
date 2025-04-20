"""
Data integration module for Cashflow trading system.

This module handles real-time and historical data fetching, processing,
and storage for the HYPE trading pair on Hyperliquid.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from hyperliquid.info import Info

# Set up SQLAlchemy models
Base = declarative_base()

class OHLCVData(Base):
    """Model for storing OHLCV candle data"""
    __tablename__ = 'ohlcv_data'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, index=True)
    interval = Column(String)  # e.g., "1m", "5m"
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)


class DataManager:
    """
    Manages market data for the trading system, including real-time
    WebSocket streams and historical data retrieval/storage.
    """
    def __init__(self, db_path: str = "data/market_data.db"):
        self.info = Info()
        self.db_engine = create_engine(f"sqlite:///{db_path}")
        self.Session = sessionmaker(bind=self.db_engine)
        
        # Caches for real-time data
        self.order_book_cache = {}
        self.candle_cache = {
            "1m": pd.DataFrame(),
            "5m": pd.DataFrame()
        }
        
        # WebSocket connection tasks
        self._websocket_tasks = []
        self.logger = logging.getLogger("data_manager")
        
        # Create database tables
        Base.metadata.create_all(self.db_engine)
        
    async def initialize(self):
        """Initialize data connections and caches"""
        # Fetch initial historical data
        await self.fetch_historical_data("1m", days=7)
        await self.fetch_historical_data("5m", days=30)
        
        # Start websocket connections
        self._websocket_tasks.append(
            asyncio.create_task(self._maintain_orderbook_stream())
        )
        self._websocket_tasks.append(
            asyncio.create_task(self._maintain_trade_stream())
        )
        
        self.logger.info("DataManager initialized successfully")
        
    async def fetch_historical_data(self, interval: str, days: int = 30) -> pd.DataFrame:
        """
        Fetch historical OHLCV data and store in database
        
        Args:
            interval: Candle interval (e.g., "1m", "5m")
            days: Number of days of historical data to fetch
            
        Returns:
            DataFrame containing the historical data
        """
        self.logger.info(f"Fetching {days} days of {interval} historical data")
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Query Hyperliquid API for historical data
        # Using the updated API method candles_snapshot with correct parameters
        end_time_ms = int(end_time.timestamp() * 1000)
        start_time_ms = int(start_time.timestamp() * 1000)
        # Use the correct spot trading pair format 'HYPE/USDC'
        candles = self.info.candles_snapshot("HYPE/USDC", interval, start_time_ms, end_time_ms)
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        
        # Ensure numeric columns are converted to float
        numeric_columns = ['o', 'h', 'l', 'c', 'v']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        # Store in database
        session = self.Session()
        try:
            for _, row in df.iterrows():
                # Handle the new candle data format from Hyperliquid API
                # The API returns: 't' (start time), 'T' (end time), 's' (symbol), 'i' (interval),
                # 'o' (open), 'c' (close), 'h' (high), 'l' (low), 'v' (volume), 'n' (number of trades)
                ohlcv = OHLCVData(
                    timestamp=datetime.fromtimestamp(row['t'] / 1000),
                    interval=interval,
                    open=float(row['o']),
                    high=float(row['h']),
                    low=float(row['l']),
                    close=float(row['c']),
                    volume=float(row['v'])
                )
                session.add(ohlcv)
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error storing historical data: {e}")
        finally:
            session.close()
            
        # Update cache
        self.candle_cache[interval] = df
        return df
        
    async def _maintain_orderbook_stream(self):
        """Maintain a persistent connection to the order book stream"""
        reconnect_delay = 1.0
        max_reconnect_delay = 60.0
        
        # Define callback function for order book updates
        def orderbook_callback(update):
            self._process_orderbook_update(update)
        
        while True:
            try:
                self.logger.info("Connecting to order book stream...")
                # Use the updated subscribe method with a callback
                subscription_id = self.info.subscribe({"type": "l2Book", "coin": "HYPE/USDC"}, orderbook_callback)
                # Wait indefinitely - the callback will handle updates
                await asyncio.sleep(3600)  # Sleep for an hour, will reconnect if there's an error
                reconnect_delay = 1.0  # Reset delay on successful connection
            except Exception as e:
                self.logger.error(f"Order book stream error: {e}")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
    
    async def _maintain_trade_stream(self):
        """Maintain a persistent connection to the trades stream"""
        reconnect_delay = 1.0
        max_reconnect_delay = 60.0
        
        # Define callback function for trade updates
        def trade_callback(update):
            self._process_trade_update(update)
        
        while True:
            try:
                self.logger.info("Connecting to trades stream...")
                # Use the updated subscribe method with a callback
                subscription_id = self.info.subscribe({"type": "trades", "coin": "HYPE/USDC"}, trade_callback)
                # Wait indefinitely - the callback will handle updates
                await asyncio.sleep(3600)  # Sleep for an hour, will reconnect if there's an error
                reconnect_delay = 1.0  # Reset delay on successful connection
            except Exception as e:
                self.logger.error(f"Trades stream error: {e}")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
    
    def _process_orderbook_update(self, update: Dict[str, Any]):
        """Process an order book update and update the cache"""
        # Update the cached order book
        self.order_book_cache = update
        
        # Calculate derived metrics like spread, depth, etc.
        # This will be used by the execution engine for liquidity-adaptive orders
        
    def _process_trade_update(self, update: Dict[str, Any]):
        """Process a trade update and update candles"""
        # Update 1m and 5m candles based on trade data
        try:
            # Ensure numeric values are properly converted to floats
            if 'price' in update:
                update['price'] = float(update['price'])
            if 'size' in update:
                update['size'] = float(update['size'])
                
            # If we have candle updates in the trade data
            if 'candle' in update:
                candle = update['candle']
                interval = candle.get('i', '1m')  # Default to 1m if not specified
                
                # Convert numeric values to float
                numeric_keys = ['o', 'h', 'l', 'c', 'v']
                for key in numeric_keys:
                    if key in candle:
                        candle[key] = float(candle[key])
                
                # Update the appropriate candle cache
                if interval in self.candle_cache:
                    # Convert to DataFrame and append to cache
                    candle_df = pd.DataFrame([candle])
                    self.candle_cache[interval] = pd.concat([self.candle_cache[interval], candle_df])
                    
                    # Keep only the most recent candles (e.g., last 1000)
                    max_candles = 1000
                    if len(self.candle_cache[interval]) > max_candles:
                        self.candle_cache[interval] = self.candle_cache[interval].tail(max_candles)
        except Exception as e:
            self.logger.error(f"Error processing trade update: {e}")
        
    def get_current_orderbook(self) -> Dict[str, Any]:
        """Get the latest order book snapshot"""
        return self.order_book_cache
    
    def get_candles(self, interval: str, limit: int = 100) -> pd.DataFrame:
        """Get the latest candles from cache"""
        if interval not in self.candle_cache:
            raise ValueError(f"Unsupported interval: {interval}")
        
        return self.candle_cache[interval].tail(limit)
    
    def close(self):
        """Close all connections and tasks"""
        for task in self._websocket_tasks:
            task.cancel()
        
        self.logger.info("DataManager closed")
