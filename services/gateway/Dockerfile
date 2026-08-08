FROM python:3.11-slim
WORKDIR /app
COPY services/gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir 'pydantic[email]' asyncpg python-multipart
COPY services/shared /app/shared
COPY services/cost-tracker /app/services/cost_tracker
COPY services/agent-host /app/services/agent_host
COPY services/rag-pipeline /app/services/rag_pipeline
COPY services/accuracy-monitor /app/services/accuracy_monitor
COPY services/gateway .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN addgroup --system appgroup && adduser --system --no-create-home --ingroup appgroup appuser
RUN mkdir -p /app/chroma_db && chown -R appuser:appgroup /app/chroma_db && chown appuser:appgroup /app
USER appuser
