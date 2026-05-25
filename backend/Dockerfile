# Use ocrmypdf's official image which already has tesseract + ghostscript
FROM jbarlow83/ocrmypdf

# Set working directory
WORKDIR /app

# Install pip then dependencies
COPY requirements.txt .
RUN python3 -m ensurepip && python3 -m pip install -r requirements.txt

# Copy all backend files
COPY . .

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]