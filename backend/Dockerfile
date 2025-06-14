# Use official Python image
FROM python:3.11-slim

# Set working dir
WORKDIR /app

# Install system deps (if any)
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port
EXPOSE 5000

# Start Flask API
CMD ["python", "app.py"]