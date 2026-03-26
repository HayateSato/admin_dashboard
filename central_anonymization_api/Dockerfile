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
# core/ includes the bundled ECG_Generalization_hierarchy.csv — no manual file placement needed
COPY server/ ./server/
COPY core/   ./core/
COPY client/ ./client/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HIERARCHY_CSV_PATH=/app/core/ECG_Generalization_hierarchy.csv

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:8080/health || exit 1

CMD ["python", "server/main.py"]
