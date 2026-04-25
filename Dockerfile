FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8080

# Use a production-ready server and listen on the port provided by Cloud Run
# We use 0.0.0.0 to ensure it's reachable externally
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"
