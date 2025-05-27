FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Explicitly add /app/src to PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app/src"

# Install Poetry
RUN pip install --no-cache-dir poetry

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock /app/

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

# Copy source code
COPY . /app

# Expose port
EXPOSE 8000

# Default command
CMD ["poetry", "run", "uvicorn", "auth_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
