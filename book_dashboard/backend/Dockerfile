FROM python:3.11-slim

WORKDIR /app

# Install build essentials for C-extensions (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# 1. Install dependencies
COPY book_dashboard/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy the shared framework (Keep it in /app/book_framework)
COPY book_framework/ ./book_framework/

# 3. Copy the actual backend source
COPY book_dashboard/backend/ .

# Ensure the app can see both folders
ENV PYTHONPATH=/app

EXPOSE 8000

# We use the default path; Compose will override the DB path env
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]