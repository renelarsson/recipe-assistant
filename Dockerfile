FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (libpq-dev and gcc are needed for psycopg2 (PostgreSQL driver))
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install pipenv
RUN pip install pipenv

# Copy Pipfile and Pipfile.lock first for better caching
COPY Pipfile Pipfile.lock ./

# Install Python dependencies
RUN pipenv install --deploy --ignore-pipfile --system

# Copy application code and data
COPY recipe_assistant ./recipe_assistant
COPY data ./data

# Expose the Flask/Gunicorn port
EXPOSE 5000

# Set environment variables (set PYTHONUNBUFFERED for better logging in Docker)
ENV PYTHONUNBUFFERED=1

# Default command to run the API with Gunicorn (the Gunicorn entrypoint)
CMD gunicorn --bind 0.0.0.0:5000 recipe_assistant.app:app