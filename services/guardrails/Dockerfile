FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/guardrails/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/shared
COPY services/guardrails .

RUN addgroup --system appgroup && adduser --system --no-create-home --ingroup appgroup appuser && \
    mkdir -p /home/appuser/.cache/huggingface && \
    chown -R appuser:appgroup /home/appuser

ENV HF_HOME=/home/appuser/.cache/huggingface
ENV TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface/transformers
ENV MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-http://mlflow:5000}
ENV MLFLOW_EXPERIMENT_NAME=${MLFLOW_EXPERIMENT_NAME:-northguard-models}
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV SIDECAR_AUTH_TOKEN=${SIDECAR_AUTH_TOKEN:-default_dev_token_change_in_production}

# Pre‑download BERT toxicity model as appuser (with retry for network flakiness)
USER appuser
RUN for i in 1 2 3; do \
        python -c "from transformers import pipeline; pipeline('text-classification', model='unitary/toxic-bert')" && break || \
        (echo "Attempt $i failed, retrying in 5s..." && sleep 5); \
    done

# Switch back to root for system-level operations
USER root
RUN mkdir -p /app/chroma_db && chown -R appuser:appgroup /app/chroma_db
USER appuser

CMD ["python", "worker.py"]
