
# Multi-stage Docker build for JOJI Oi system
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY setup.py README.md ./

# Install the package
RUN pip install -e .

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOJIAI_ENV=production

# Create non-root user
RUN groupadd -r jojiai && useradd -r -g jojiai jojiai

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /app/data /app/logs /app/backups && \
    chown -R jojiai:jojiai /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/src /app/src

# Set working directory
WORKDIR /app

# Switch to non-root user
USER jojiai

# Expose ports
EXPOSE 8000 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "jojiai.core"]

# Development stage
FROM builder as development

# Install development dependencies
RUN pip install -r requirements-dev.txt

# Copy test files
COPY tests/ ./tests/

# Set development environment
ENV JOJIAI_ENV=development

# Default command for development
CMD ["pytest", "tests/", "-v"]
