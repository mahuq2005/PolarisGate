FROM python:3.11-slim
WORKDIR /app
COPY services/gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir 'pydantic[email]' asyncpg python-multipart
COPY services/shared /app/shared
COPY services/gateway .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN addgroup --system appgroup && adduser --system --no-create-home --ingroup appgroup appuser
RUN mkdir -p /app/chroma_db && chown -R appuser:appgroup /app/chroma_db && chown appuser:appgroup /app
USER appuser
