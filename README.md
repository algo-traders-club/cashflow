# Cashflow Trading Agent

Autonomous spot trading system for HYPE/USDC on Hyperliquid L1.

## Overview

Cashflow is a high-performance trading system that implements a hybrid strategy combining mean reversion and trend following for the HYPE/USDC spot trading pair on Hyperliquid. The system features liquidity-adaptive execution, comprehensive risk management, and a monitoring API.

The system supports both conservative and aggressive trading configurations, with the aggressive mode offering larger position sizes, more relaxed signal generation parameters, and extended profit targets while maintaining proper risk controls.

### Latest Improvements

- **Enhanced Data Processing**: Fixed numeric data conversion for proper handling of candle data in spot trading format
- **Improved Error Handling**: Added robust error handling for WebSocket connections and trade updates
- **Debug Endpoint**: Added a new `/debug` API endpoint for real-time diagnostics of trading parameters and market conditions
- **Aggressive Trading Parameters**: Implemented and tested more aggressive trading configuration with:
  - Reduced RSI thresholds (oversold: 30→25, overbought: 70→75)
  - Decreased Bollinger Band std_dev from 1.5 to 1.25
  - Relaxed volume confirmation threshold from 1.5x to 1.25x average
  - Added 20% signal strength boost for more aggressive trading
  - Increased max_position_size from 2% to 5% of portfolio
  - Raised max_trade_risk from 0.5% to 1% per trade

## Features

- Real-time market data integration via WebSockets
- Enhanced hybrid trading strategy with volume confirmation and time-based filters
- Adaptive execution strategy that dynamically selects optimal order types
- Volatility-adjusted position sizing and enhanced risk management
- Comprehensive performance metrics and monitoring
- FastAPI-based monitoring and control interface with diagnostic endpoints
- Historical data storage and analysis
- Support for both conservative and aggressive trading modes

## Project Structure

```
cashflow/
├── src/
│   ├── agent/          # Core trading agent logic
│   │   ├── __init__.py
│   │   ├── trading_agent.py
│   │   └── trading_loop.py
│   ├── execution/      # Order execution and management
│   │   ├── engine.py
│   │   ├── orders.py
│   │   ├── risk.py
│   │   ├── strategies.py
│   │   ├── enhanced_risk.py      # Enhanced risk management
│   │   └── adaptive_strategy.py  # Adaptive execution strategy
│   ├── strategy/       # Trading strategy implementation
│   │   ├── __init__.py
│   │   └── enhanced_strategy.py  # Enhanced strategy with filters
│   ├── utils/          # Utility functions
│   │   ├── __init__.py
│   │   └── metrics.py  # Enhanced metrics collection
│   ├── __init__.py     # Package initialization
│   ├── api.py          # FastAPI endpoints
│   ├── data.py         # Data fetching and preprocessing
│   └── main.py         # Main entry point
├── config/
│   ├── config.yaml           # Base configuration
│   ├── enhanced_config.yaml  # Enhanced configuration
│   └── .env                  # API keys and secrets
├── data/               # Storage for market data
├── logs/               # Application logs
├── tests/              # Unit and integration tests
├── requirements.txt    # Python dependencies
├── run_trading.py      # Script to run the trading system
└── README.md           # Project documentation

## API Endpoints

The trading system provides the following RESTful API endpoints:

- `GET /` - API root, returns basic information about the API
- `GET /status` - Get the current system status, uptime, and trading statistics
- `GET /portfolio` - Get the current portfolio status, positions, and PnL
- `GET /trades` - Get recent trades executed by the system
- `GET /debug` - Get detailed diagnostic information about the trading system
- `POST /start` - Start the trading agent
- `POST /stop` - Stop the trading agent

## Configuration Options

The system supports two main configuration modes:

### Conservative Mode (config.yaml)

- **Strategy Parameters**:
  - RSI thresholds: 30 (oversold), 70 (overbought)
  - Bollinger Band std_dev: 1.5
  - Volume confirmation threshold: 1.5x average

- **Risk Management**:
  - max_position_size: 2% of portfolio
  - max_trade_risk: 0.5% per trade
  - circuit_breaker_drawdown: 2% daily
  - circuit_breaker_consecutive_losses: 2

### Aggressive Mode (enhanced_config.yaml)

- **Strategy Parameters**:
  - RSI thresholds: 25 (oversold), 75 (overbought)
  - Bollinger Band std_dev: 1.25
  - Volume confirmation threshold: 1.25x average
  - Signal strength boost: 20%

- **Risk Management**:
  - max_position_size: 5% of portfolio
  - max_trade_risk: 1% per trade
  - circuit_breaker_drawdown: 5% daily
  - circuit_breaker_consecutive_losses: 3
  - volatility_ceiling: 0.08 (increased from 0.05)

## Usage

```bash
# Start with conservative configuration
python run_trading.py --config config/config.yaml --api-port 9001

# Start with aggressive configuration
python run_trading.py --config config/enhanced_config.yaml --api-port 9001
```

## Requirements

- Python 3.10+
- FastAPI
- Hyperliquid Python SDK
- Pandas
- NumPy
- Prometheus Client
└── README.md           # Setup and usage instructions
```

## Setup

### Prerequisites

- Python 3.10+ installed
- Hyperliquid account with API keys
- USDC funds in your Hyperliquid wallet

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/cashflow.git
   cd cashflow
   ```

2. Create and activate a virtual environment
   ```bash
   python -m venv fresh_venv
   source fresh_venv/bin/activate  # On Windows: fresh_venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your environment variables
   ```bash
   # Create .env file in the config directory
   mkdir -p config
   echo "PRIVATE_KEY=your_hyperliquid_private_key" > config/.env
   echo "JWT_SECRET_KEY=your_jwt_secret_key" >> config/.env
   ```

## Configuration

The trading system can be configured through either `config/config.yaml` (basic configuration) or `config/enhanced_config.yaml` (enhanced features). The system is specifically configured for spot trading HYPE/USDC on Hyperliquid, not perpetual futures.

Key parameters include:

### Risk Management Parameters

#### Conservative Configuration
```yaml
execution:
  max_position_size: 0.02       # 2% of portfolio
  max_trade_risk: 0.005         # 0.5% per trade
  circuit_breaker_drawdown: 0.02  # 2% daily drawdown limit
  circuit_breaker_consecutive_losses: 2  # Stop after 2 consecutive losses
```

#### Aggressive Configuration
```yaml
execution:
  max_position_size: 0.05       # 5% of portfolio
  max_trade_risk: 0.01          # 1% per trade
  circuit_breaker_drawdown: 0.05  # 5% daily drawdown limit
  circuit_breaker_consecutive_losses: 3  # Stop after 3 consecutive losses
```

### Strategy Parameters

#### Conservative Configuration
```yaml
strategy:
  bb_period: 20
  bb_std_dev: 1.5
  rsi_period: 14
  rsi_oversold: 30
  rsi_overbought: 70
  ema_period: 50
  adx_period: 14
  adx_threshold: 25
  
  # Exit parameters
  atr_period: 14
  take_profit_atr_multiple: 1.2
  stop_loss_atr_multiple: 0.4
  time_exit_minutes: 15
```

#### Aggressive Configuration
```yaml
strategy:
  bb_period: 20
  bb_std_dev: 1.25  # Reduced for more signals
  rsi_period: 14
  rsi_oversold: 25   # Reduced for more aggressive buy signals
  rsi_overbought: 75  # Increased for more aggressive sell signals
  ema_period: 50
  adx_period: 14
  adx_threshold: 25
  
  # Exit parameters
  atr_period: 14
  take_profit_atr_multiple: 1.5  # Increased for larger profits
  stop_loss_atr_multiple: 0.6    # Widened for more room
  time_exit_minutes: 30          # Extended for longer trades
```

### Execution Parameters

#### Conservative Configuration
```yaml
execution:
  # Adaptive execution
  adaptive_execution: true
  min_liquidity_score: 0.3
  max_volatility_for_market_orders: 0.7
  size_threshold_for_twap: 0.01  # 1% of avg volume

  # Enhanced risk parameters
  volatility_lookback: 14  # days
  max_volatility_adjustment: 0.5  # 50% size reduction
  volatility_floor: 0.01  # 1% daily volatility
  volatility_ceiling: 0.05  # 5% daily volatility
```

#### Aggressive Configuration
```yaml
execution:
  # Adaptive execution
  adaptive_execution: true
  min_liquidity_score: 0.2  # Reduced for trading in less liquid conditions
  max_volatility_for_market_orders: 0.9  # Increased for more market orders
  size_threshold_for_twap: 0.02  # 2% of avg volume

  # Enhanced risk parameters
  volatility_lookback: 14  # days
  max_volatility_adjustment: 0.3  # 30% size reduction
  volatility_floor: 0.01  # 1% daily volatility
  volatility_ceiling: 0.08  # 8% daily volatility
```

### Metrics Configuration

#### Basic Metrics
```yaml
metrics:
  enabled: true
  prometheus_port: 9090
  history_size: 1000  # Maximum number of trades to keep in memory
```

#### Advanced Metrics (Aggressive Configuration)
```yaml
metrics:
  enabled: true
  prometheus_port: 9090
  history_size: 1000  # Maximum number of trades to keep in memory
  
  # Aggressive trading metrics
  track_aggression_ratio: true  # Trades taken vs opportunities
  track_position_distribution: true  # Position size distribution
  track_risk_adjusted_returns: true  # Risk-adjusted return metrics
  track_aggression_coefficient: true  # Actual vs max possible position sizing
```

## Spot Trading Configuration

The Cashflow trading agent is configured to trade on the spot market (HYPE/USDC) rather than perpetual futures. This configuration includes:

- Proper trading pair format: "HYPE/USDC" for all API calls
- Correct candle data format handling for spot markets
- Appropriate order execution methods for spot trading
- Spot-specific market data subscriptions

## Running the Trading System

### Configuration Selection

You can choose between conservative and aggressive trading configurations:

```bash
# Conservative configuration
python run_trading.py --config config/config.yaml

# Aggressive configuration
python run_trading.py --config config/enhanced_config.yaml
```

### Standard Configuration

Run the system with the standard configuration:

```bash
source fresh_venv/bin/activate
python run_trading.py --api-port 9000
```

### Enhanced Configuration

Run the system with the enhanced configuration that includes all advanced features:

```bash
source fresh_venv/bin/activate
python run_trading.py --config config/enhanced_config.yaml --api-port 9000
```

### API-Only Mode (Recommended for Production)

Run the system in API-only mode, which starts the API server without automatically starting trading:

```bash
source fresh_venv/bin/activate
python run_trading.py --config config/enhanced_config.yaml --api-only --api-port 9000
```

This will start the API server on port 9000. You can then use the API to control the trading system.

### Full Trading Mode

To start the system with trading enabled immediately:

```bash
source fresh_venv/bin/activate
python run_trading.py --config config/enhanced_config.yaml --start-trading --api-port 9000
```

## Controlling the Trading System

### Using the API

The Cashflow trading system provides a RESTful API for monitoring and controlling the trading operations.

#### Starting Trading

```bash
curl -X POST http://localhost:9000/start
```

#### Stopping Trading

```bash
curl -X POST http://localhost:9000/stop
```

#### Checking System Status

```bash
curl http://localhost:9000/status
```

Response example:
```json
{
  "status": "active",
  "uptime_seconds": 3600,
  "trades_today": 5,
  "win_rate": 0.6,
  "last_signal": {
    "type": "buy",
    "strength": 0.8,
    "price": 16.75
  }
}
```

#### Checking Portfolio Status

```bash
curl http://localhost:9000/portfolio
```

Response example:
```json
{
  "portfolio_value": 22.5,
  "positions": {
    "HYPE": 0.5
  },
  "daily_pnl": 0.5,
  "daily_pnl_percent": 2.27,
  "trading_enabled": true
}
```

#### Viewing Recent Trades

```bash
curl http://localhost:9000/trades
```

#### Updating Strategy Configuration

```bash
curl -X POST http://localhost:9000/config/strategy \
  -H "Content-Type: application/json" \
  -d '{"rsi_threshold_buy": 25, "rsi_threshold_sell": 75}'
```

#### Updating Risk Configuration

```bash
curl -X POST http://localhost:9000/config/risk \
  -H "Content-Type: application/json" \
  -d '{"max_position_size": 0.01, "max_trade_risk": 0.003}'
```

#### Resetting Circuit Breaker

If the circuit breaker has been triggered (due to consecutive losses or drawdown limit):

```bash
curl -X POST http://localhost:9000/reset
```

## Monitoring and Logs

The system logs detailed information to the `logs/` directory:

- `logs/cashflow_trading.log`: Main application log
- `logs/cashflow_YYYYMMDD.log`: Daily logs with detailed trading information

Monitor these logs for insights into the system's operation and any potential issues.

## Risk Management

The Cashflow trading system includes several risk management features:

1. **Position Size Limits**: Controls the maximum size of any single position as a percentage of your portfolio.

2. **Per-Trade Risk Limits**: Limits the risk exposure of any single trade.

3. **Circuit Breakers**:
   - Daily drawdown limit: Stops trading if daily losses exceed a configurable threshold.
   - Consecutive loss limit: Stops trading after a specified number of consecutive losses.

4. **Take Profit and Stop Loss**: Automatically exits positions based on ATR multiples.

5. **Time-Based Exits**: Exits positions that have been open for too long.

## Troubleshooting

### Common Issues

1. **API Connection Issues**:
   - Ensure your Hyperliquid private key is correctly set in `config/.env`
   - Check network connectivity to Hyperliquid API

2. **Port Already in Use**:
   - If you see "address already in use" errors, specify a different port with `--api-port`

3. **Trading Not Starting**:
   - Check logs for error messages
   - Verify your account has sufficient funds
   - Ensure circuit breakers haven't been triggered

## License

MIT
