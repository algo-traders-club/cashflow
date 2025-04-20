FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY run_trading.py cashflow.sh ./
COPY src ./src
COPY config ./config

# Create necessary directories
RUN mkdir -p data logs

# Make the shell script executable
RUN chmod +x cashflow.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose API port
EXPOSE 9001

# Set default configuration to enhanced (aggressive) mode
ENV CONFIG_FILE=config/enhanced_config.yaml
ENV API_PORT=9001

# Run the application
CMD python run_trading.py --config $CONFIG_FILE --api-port $API_PORT
