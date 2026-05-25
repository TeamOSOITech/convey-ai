FROM jbarlow83/ocrmypdf

WORKDIR /app

COPY requirements.txt .
RUN /app/.venv/bin/pip install -r requirements.txt

COPY . .

CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]