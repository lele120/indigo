FROM python:3.11-slim

# Install system dependencies in one layer
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Layer 1: Heavy ML dependencies (cached, rarely changes)
# This layer includes PyTorch (~530MB), CUDA libs (~366MB), sentence-transformers, etc.
# Only rebuilds when requirements-base.txt changes
COPY requirements-base.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements-base.txt

# Layer 2: Lightweight app dependencies (rebuilds more frequently)
# This layer includes fastapi, asyncpg, sqlalchemy, etc.
# Only rebuilds when requirements-app.txt changes
COPY requirements-app.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements-app.txt

# Copy application code (changes frequently, so last)
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
