# Dockerfile for FL gRPC Server
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy FL server requirements
COPY requirements_fl.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_fl.txt

# Copy FL server files
COPY . .

# Create directories for models and logs
RUN mkdir -p /app/models /app/logs

# Expose gRPC port
EXPOSE 50051

# Set environment variables
ENV FL_SERVER_HOST=0.0.0.0
ENV FL_SERVER_PORT=50051
ENV PYTHONUNBUFFERED=1

# Run the FL gRPC server
CMD ["python", "fl_grpc_server.py"]
