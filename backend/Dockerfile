# Use a Python image that has tesseract available
FROM python:3.11-slim

# Install tesseract and ghostscript via apt
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy all backend files
COPY . .

# Start the server
CMD uvicorn main:app --host 0.0.0.0 --port $PORT