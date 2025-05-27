FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Explicitly add /app/src to PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app/src"

# Set pip timeout
ENV PIP_DEFAULT_TIMEOUT=100

# Install Poetry
RUN pip install --no-cache-dir poetry

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock /app/

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi --with dev

# Copy source code
COPY . /app

# Expose port
EXPOSE 8000

# Default command
CMD ["poetry", "run", "uvicorn", "auth_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
