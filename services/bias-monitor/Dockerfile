FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY services/bias-monitor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir asyncpg tenacity redis 'pydantic[email]'
COPY services/shared /app/shared
COPY services/bias-monitor .
RUN addgroup --system appgroup && adduser --system --no-create-home --ingroup appgroup appuser
RUN mkdir -p /app/chroma_db && chown -R appuser:appgroup /app/chroma_db
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
