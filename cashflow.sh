#!/bin/bash
# Cashflow Trading System Management Script

# Default values
CONFIG_PATH="config/config.yaml"
API_PORT=8000
MODE="api-only"

# Help function
show_help() {
    echo "Cashflow Trading System Management Script"
    echo ""
    echo "Usage: ./cashflow.sh [command] [options]"
    echo ""
    echo "Commands:"
    echo "  start         Start the trading system"
    echo "  stop          Stop the trading system (if running)"
    echo "  status        Check the status of the trading system"
    echo "  logs          View the logs"
    echo "  setup         Set up the environment"
    echo ""
    echo "Options:"
    echo "  --mode        Trading mode: api-only, trading, simulation (default: api-only)"
    echo "  --config      Path to config file (default: config/config.yaml)"
    echo "  --port        API port (default: 8000)"
    echo ""
    echo "Examples:"
    echo "  ./cashflow.sh start --mode trading"
    echo "  ./cashflow.sh start --mode api-only --port 8080"
    echo "  ./cashflow.sh logs"
}

# Parse command line arguments
COMMAND=$1
shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            MODE=$2
            shift 2
            ;;
        --config)
            CONFIG_PATH=$2
            shift 2
            ;;
        --port)
            API_PORT=$2
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Create necessary directories
mkdir -p logs data

# Check if .env file exists
if [ ! -f "config/.env" ]; then
    echo "Error: config/.env file not found"
    echo "Please create the .env file with your API keys"
    exit 1
fi

# Execute command
case "$COMMAND" in
    start)
        echo "Starting Cashflow Trading System..."
        
        # Check if PID file exists
        if [ -f "cashflow.pid" ]; then
            PID=$(cat cashflow.pid)
            if ps -p $PID > /dev/null; then
                echo "Cashflow is already running with PID $PID"
                exit 1
            else
                echo "Removing stale PID file"
                rm cashflow.pid
            fi
        fi
        
        # Activate virtual environment if it exists
        if [ -d ".venv" ]; then
            source .venv/bin/activate
        fi
        
        # Start with appropriate mode
        if [ "$MODE" == "trading" ]; then
            echo "Starting in trading mode"
            python run_trading.py --config $CONFIG_PATH --api-port $API_PORT --start-trading &
        elif [ "$MODE" == "api-only" ]; then
            echo "Starting in API-only mode"
            python run_trading.py --config $CONFIG_PATH --api-port $API_PORT --api-only &
        elif [ "$MODE" == "simulation" ]; then
            echo "Starting in simulation mode"
            python run_trading.py --config $CONFIG_PATH --api-port $API_PORT --simulation &
        else
            echo "Unknown mode: $MODE"
            exit 1
        fi
        
        # Save PID
        echo $! > cashflow.pid
        echo "Cashflow started with PID $(cat cashflow.pid)"
        ;;
        
    stop)
        echo "Stopping Cashflow Trading System..."
        if [ -f "cashflow.pid" ]; then
            PID=$(cat cashflow.pid)
            if ps -p $PID > /dev/null; then
                kill $PID
                echo "Sent stop signal to process $PID"
                # Wait for process to terminate
                for i in {1..10}; do
                    if ! ps -p $PID > /dev/null; then
                        break
                    fi
                    echo "Waiting for process to terminate..."
                    sleep 1
                done
                
                # Force kill if still running
                if ps -p $PID > /dev/null; then
                    echo "Process still running, force killing..."
                    kill -9 $PID
                fi
                
                rm cashflow.pid
                echo "Cashflow stopped"
            else
                echo "No running process found with PID $PID"
                rm cashflow.pid
            fi
        else
            echo "No PID file found, Cashflow may not be running"
        fi
        ;;
        
    status)
        if [ -f "cashflow.pid" ]; then
            PID=$(cat cashflow.pid)
            if ps -p $PID > /dev/null; then
                echo "Cashflow is running with PID $PID"
                # Try to get status from API
                STATUS=$(curl -s http://localhost:$API_PORT/status 2>/dev/null)
                if [ $? -eq 0 ]; then
                    echo "API Status: $STATUS"
                else
                    echo "API is not responding"
                fi
            else
                echo "Cashflow is not running (stale PID file found)"
            fi
        else
            echo "Cashflow is not running (no PID file found)"
        fi
        ;;
        
    logs)
        if [ -f "logs/cashflow_trading.log" ]; then
            tail -f logs/cashflow_trading.log
        else
            echo "No log file found"
        fi
        ;;
        
    setup)
        echo "Setting up Cashflow Trading System..."
        
        # Check if Python is installed
        if ! command -v python3 &> /dev/null; then
            echo "Python 3 is not installed"
            exit 1
        fi
        
        # Check if UV is installed
        if ! command -v uv &> /dev/null; then
            echo "UV is not installed. Installing..."
            curl -sSf https://install.python-uv.org | python3
        fi
        
        # Install dependencies
        echo "Installing dependencies..."
        uv pip install -e .
        
        echo "Setup complete!"
        echo "Please edit config/.env to add your API keys"
        ;;
        
    *)
        echo "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac

exit 0
