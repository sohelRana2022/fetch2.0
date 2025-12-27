# Use official Python 3.11 slim image
FROM python:3.11-slim

# Install ffmpeg and system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements.txt and install Python packages
COPY requirements.txt .
RUN python -m venv /app/.venv
RUN /app/.venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Expose port for Railway
EXPOSE 5000

# Run the app using gunicorn
CMD ["/app/.venv/bin/gunicorn", "-b", "0.0.0.0:5000", "app:app"]
