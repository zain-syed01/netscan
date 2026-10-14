FROM python:3.12-slim

WORKDIR /app

# Install deps first so Docker can cache this layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as a non-root user (good habit for containers)
RUN useradd -m -u 1000 scanner && chown -R scanner:scanner /app
USER scanner

EXPOSE 8765

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
