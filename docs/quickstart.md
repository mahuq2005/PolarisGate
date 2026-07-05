# Quickstart Guide

This guide will get PolarisGate up and running in under 5 minutes.

## Prerequisites

- **Docker** v24+ and **Docker Compose** v2+
- **Git**
- **Make** (recommended, but commands work without it)
- **8 GB RAM** minimum (16 GB recommended for ML models)

## Step 1: Clone & Setup

```bash
git clone https://github.com/polarisgate/polarisgate.git
cd polarisgate
cp .env.example .env
make setup
```

The `make setup` command will:
1. Copy `.env.example` to `.env` (if not exists)
2. Generate a random JWT secret
3. Create necessary directories

> **Edit `.env`** to configure secrets, API keys, and feature flags before proceeding.

## Step 2: Build & Start

```bash
# Build all Docker images
make build

# Start all services in the background
make up

# Check that everything is running
make status
```

Expected output:
```
NAME                     STATUS           PORTS
polarisgate-gateway       Up              0.0.0.0:8000->8000
polarisgate-guardrails    Up              0.0.0.0:8005->8005
polarisgate-hallucination Up              0.0.0.0:8008->8008
polarisgate-nginx         Up              0.0.0.0:443->443, 80->80
polarisgate-postgres      Up              0.0.0.0:5432->5432
polarisgate-redis         Up              0.0.0.0:6379->6379
...
```

> **Note**: First startup may take 1-3 minutes as services initialize and health checks pass.

## Step 3: Verify Health

```bash
# Check the gateway health endpoint
curl -s http://localhost:8000/health | jq .
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.1.0",
  "services": {
    "postgres": "connected",
    "redis": "connected",
    "ollama": "connected"
  }
}
```

## Step 4: Get an Auth Token

```bash
# Default admin credentials (printed in gateway logs on first startup)
# Or create a user via the API:
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "polarisgate"}' | jq -r '.access_token'
```

## Step 5: Run a Guardrails Check

```bash
# Set your token
TOKEN="<access-token-from-step-4>"

# Toxicity check
curl -s -X POST http://localhost:8000/api/v1/guardrails/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "text": "I am feeling great today and enjoy working with AI!",
    "checks": ["toxicity", "pii", "sentiment"]
  }' | jq .
```

## Step 6: Test Hallucination Detection

```bash
# The hallucination detector requires a context and a response to compare
curl -s -X POST http://localhost:8008/api/v1/hallucination/detect \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "context": "The sky is blue and clouds are white on a sunny day.",
    "response": "The sky is blue.",
    "domain": "general"
  }' | jq .
```

## Step 7: Open the Dashboard

Navigate to **https://localhost** in your browser.

> **Note**: Since PolarisGate uses self-signed certificates by default, you'll need to accept the browser warning in development.

## Step 8: Run Accuracy Tests

```bash
# Fast smoke tests (keyword toxicity, Luhn PII)
make test-accuracy

# Full validation (BERT API, RoBERTa API, cascade pipeline)
make test-accuracy-full
```

## What's Next?

| Resource | Description |
|----------|-------------|
| [Production Deployment](deployment/production.md) | Deploy PolarisGate in production |
| [Kubernetes Guide](deployment/kubernetes.md) | Deploy on Kubernetes with Helm |
| [API Reference](api/gateway.md) | Full API documentation |
| [Architecture Overview](architecture/overview.md) | System architecture deep dive |
| [Custom Policies](../policies/) | Create custom OPA policies |
| [Model Training](../scripts/pipeline_train.sh) | Train custom toxicity/PII models |

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| Containers restarting | Port conflict | Change ports in `.env` / `docker-compose.override.yml` |
| Gateway returns 503 | Service not ready | Wait 30s, check `make status` |
| Ollama model errors | Model not pulled | Run `make ollama-pull` |
| Database connection failed | Postgres not ready | Check `make logs postgres` |
| Token invalid | JWT secret changed | Re-login or set consistent `JWT_SECRET` |

> For detailed troubleshooting, see the [Troubleshooting Guide](troubleshooting.md).