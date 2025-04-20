#!/usr/bin/env python
"""
Run the Cashflow trading system on mainnet.

This script initializes and runs the Cashflow trading system with proper
error handling and logging.
"""
import os
import sys
import asyncio
import argparse
import logging
from dotenv import load_dotenv
from src.agent import TradingAgent
from src.api import CashflowAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/cashflow_trading.log")
    ]
)
logger = logging.getLogger("run_trading")

async def main():
    """Initialize and run the trading system"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Cashflow trading system")
    parser.add_argument("--config", type=str, default="config/config.yaml", 
                      help="Path to configuration file")
    parser.add_argument("--api-port", type=int, default=8000, 
                      help="Port for the API server")
    parser.add_argument("--start-trading", action="store_true", 
                      help="Start trading immediately")
    parser.add_argument("--api-only", action="store_true", 
                      help="Run only the API server without trading")
    args = parser.parse_args()
    
    # Load environment variables from .env file
    env_path = os.path.join(os.path.dirname(args.config), ".env")
    load_dotenv(env_path)
    
    # Check for private key
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        logger.error("PRIVATE_KEY not set in .env file")
        logger.error("Please set your Hyperliquid private key in config/.env")
        return 1
    
    # Create data directories if they don't exist
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Initialize trading agent
    logger.info("Initializing trading agent")
    agent = TradingAgent(args.config)
    await agent.initialize()
    
    # Initialize API
    logger.info("Initializing API")
    api = CashflowAPI()
    api.set_trading_system(agent)
    
    # Start trading if requested
    if args.start_trading and not args.api_only:
        logger.info("Starting trading")
        await agent.start()
    
    # Run API server
    logger.info(f"Starting API server on port {args.api_port}")
    
    # Create a task for the API server
    api_task = asyncio.create_task(
        asyncio.to_thread(api.run, host="0.0.0.0", port=args.api_port)
    )
    
    try:
        # Wait for the API server to complete (which it never will unless interrupted)
        await api_task
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        if agent.is_running:
            await agent.stop()
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        # Clean up
        if agent.is_running:
            await agent.stop()
        logger.info("Trading system shut down")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down")
        sys.exit(0)
