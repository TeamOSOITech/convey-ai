# Use ocrmypdf's official image which already has tesseract + ghostscript
FROM jbarlow83/ocrmypdf

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy all backend files
COPY . .

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]