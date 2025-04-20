FROM python:3.10-slim

WORKDIR /app

# Install UV package manager
RUN pip install uv

# Copy project files
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config

# Create necessary directories
RUN mkdir -p data logs

# Install dependencies using UV
RUN uv pip install -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose API port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "src.main", "--config", "config/config.yaml"]
