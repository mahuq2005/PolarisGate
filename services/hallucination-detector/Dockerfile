FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/hallucination-detector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download DeBERTa NLI model (with retry for network flakiness)
ENV HF_HOME=/tmp/hf_cache
RUN for i in 1 2 3; do \
        python -c "from transformers import pipeline; \
        pipeline('text-classification', model='MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli')" \
        && break || (echo "Attempt $i failed, retrying in 5s..." && sleep 5); \
    done

COPY services/hallucination-detector/hd_cascade/ ./hd_cascade/

RUN addgroup --system appgroup && adduser --system --no-create-home --ingroup appgroup appuser && \
    mkdir -p /home/appuser/.cache && chown -R appuser:appgroup /home/appuser

ENV HF_HOME=/home/appuser/.cache/huggingface
ENV TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface/transformers

USER appuser

EXPOSE 8008

CMD ["uvicorn", "hd_cascade.main:app", "--host", "0.0.0.0", "--port", "8008"]
