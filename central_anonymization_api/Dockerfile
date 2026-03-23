FROM python:3.11-slim

WORKDIR /app

# wget for the HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server/ ./server/
COPY core/   ./core/
COPY client/ ./client/

# The k-anonymity algorithm requires smarko_hierarchy_ecg.csv at runtime.
# Mount it via docker-compose volume, or copy it here with:
#   COPY path/to/smarko_hierarchy_ecg.csv ./data/smarko_hierarchy_ecg.csv
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HIERARCHY_CSV_PATH=/app/data/smarko_hierarchy_ecg.csv

EXPOSE 6000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:6000/health || exit 1

CMD ["python", "server/main.py"]
