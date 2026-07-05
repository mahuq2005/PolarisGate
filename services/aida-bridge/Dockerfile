FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip

COPY services/aida-bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre‑download sentence transformer model (with retry for network flakiness)
ENV SENTENCE_TRANSFORMERS_HOME=/tmp/st_cache
RUN for i in 1 2 3; do \
        python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" && break || \
        (echo "Attempt $i failed, retrying in 5s..." && sleep 5); \
    done

# Pre‑download ChromaDB's ONNX model
ENV CHROMA_DOWNLOAD_PATH=/tmp/chroma_cache
RUN for i in 1 2 3; do \
        python -c "import chromadb; from chromadb.utils import embedding_functions; ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name='all-MiniLM-L6-v2'); client = chromadb.Client(); col = client.create_collection('dummy', embedding_function=ef); col.add(documents=['test'], ids=['1'])" && break || \
        (echo "Attempt $i failed, retrying in 5s..." && sleep 5); \
    done

COPY services/shared /app/shared
COPY services/aida-bridge .

# Create non‑root user and required directories
RUN addgroup --system appgroup && \
    adduser --system --no-create-home --ingroup appgroup appuser && \
    mkdir -p /home/appuser && \
    chown -R appuser:appgroup /home/appuser && \
    mkdir -p /app/chroma_db /app/pdfs && \
    chown -R appuser:appgroup /app/chroma_db /app/pdfs

# Set final environment variables for runtime
ENV HOME=/home/appuser
ENV HF_HOME=/home/appuser/.cache/huggingface
ENV TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface/transformers
ENV SENTENCE_TRANSFORMERS_HOME=/home/appuser/.cache/sentence_transformers
ENV CHROMA_DOWNLOAD_PATH=/home/appuser/.cache/chroma

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
