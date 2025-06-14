# Use official slim image
FROM python:3.11-slim

# Install required version of Poetry
ENV POETRY_VERSION=1.8.2

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc build-essential ca-certificates git libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Copy project files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy remaining source code
COPY . .

# Install Playwright browsers (if used)
RUN playwright install-deps
RUN playwright install chromium

# Expose port
EXPOSE 8000

# Run application with Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
