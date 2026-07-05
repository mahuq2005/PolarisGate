# Troubleshooting Guide

Common issues, debugging practices, and solutions for PolarisGate deployments.

## Table of Contents

- [Deployment Issues](#deployment-issues)
- [Service Issues](#service-issues)
- [API Issues](#api-issues)
- [ML Model Issues](#ml-model-issues)
- [Security Issues](#security-issues)
- [Database Issues](#database-issues)
- [Networking Issues](#networking-issues)
- [Debugging Tools](#debugging-tools)

---

## Deployment Issues

### Containers Exit Immediately / Restart Loop

**Symptoms**: `docker compose ps` shows containers with status "Exit" or "Restarting"

**Likely causes**:
1. **Port conflicts**: Another service is using the same port
2. **Missing dependencies**: A service depends on a resource that hasn't started
3. **Environment variables**: Missing or invalid `.env` configuration

**Solutions**:
```bash
# Check container logs
make logs <service-name>

# Check for port conflicts
lsof -i :8000  # Check if port 8000 is already in use

# Override ports in docker-compose.override.yml
cat > docker-compose.override.yml <<EOF
version: '3.8'
services:
  gateway:
    ports:
      - "8001:8000"  # Map host port 8001 to container port 8000
EOF
```

### "Service Unavailable" (503) from Gateway

**Symptoms**: Gateway returns HTTP 503

**Solutions**:
```bash
# Check which services are healthy
make status

# Check gateway logs for the specific failure
make logs gateway

# Wait for dependencies to fully initialize (especially Postgres, Redis, Ollama)
sleep 30 && make status
```

### Docker Compose v1 vs v2

If you get an error about `docker compose` not found, use the legacy syntax:
```bash
# Docker Compose v1
docker-compose up -d

# Docker Compose v2 (newer)
docker compose up -d
```

---

## Service Issues

### Gateway

| Symptom | Cause | Solution |
|---------|-------|----------|
| `401 Unauthorized` on all requests | Missing/invalid token | Get a new token via `/api/v1/auth/login` |
| `429 Too Many Requests` | Rate limit exceeded | Wait 60 seconds or increase limits in `.env` |
| Gateway crashes on startup | Database migration failed | Run `make migrate` manually |
| Slow response times | Under-provisioned resources | Increase Docker CPU/memory limits |

### Guardrails Service

| Symptom | Cause | Solution |
|---------|-------|----------|
| Toxicity check returns `error` | BERT model not loaded | Check `make logs guardrails`, wait for model download |
| PII detection misses known patterns | Regex pattern not configured | Check `policies/pii_context.yaml` |
| All checks return `error` | Guardrails service not healthy | Check `curl -s http://localhost:8005/health` |

### Hallucination Detector

| Symptom | Cause | Solution |
|---------|-------|----------|
| Cascade returns empty results | Ollama model not available | Run `make ollama-pull` |
| NLI detector fails | Cross-encoder model not downloaded | Check `make logs hallucination-detector` |
| High latency | Cascade too slow for real-time | Reduce cascade depth or use lower-tier models |

### Kill Switch

| Symptom | Cause | Solution |
|---------|-------|----------|
| Agent not being throttled | Kill switch not triggered | Check threshold in `policies/confidence_thresholds.yaml` |
| `Connection refused` on port 10001 | Kill switch not running | `docker compose up -d kill-switch` |

---

## API Issues

### Authentication

```bash
# Verify your token is valid
curl -s http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer $TOKEN"

# Get a fresh token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"polarisgate"}' | jq -r '.access_token')
```

### Common HTTP Status Codes

| Code | Meaning | Common Cause |
|------|---------|-------------|
| 200 | Success | — |
| 400 | Bad Request | Invalid JSON body, missing required fields |
| 401 | Unauthorized | Missing/invalid/expired token |
| 403 | Forbidden | Insufficient permissions (RBAC) |
| 404 | Not Found | Wrong endpoint URL |
| 422 | Unprocessable Entity | Schema validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Service-side exception |
| 502 | Bad Gateway | Upstream service unreachable |
| 503 | Service Unavailable | Service not ready or overloaded |

---

## ML Model Issues

### Ollama Models Not Available

```bash
# Pull required models manually
make ollama-pull

# Or pull specific models
docker compose exec ollama ollama pull llama3.2:1b
docker compose exec ollama ollama pull tinyllama

# Verify models are downloaded
docker compose exec ollama ollama list
```

### BERT / RoBERTa Models Fail to Load

The guardrails service downloads models on first startup. This can take 2-5 minutes.

```bash
# Check download progress
make logs guardrails

# Manually trigger model download
docker compose exec guardrails python -c "
from app.classifiers.bert_toxic import BERTToxicClassifier
c = BERTToxicClassifier()
c.load_model()
"
```

### High Model Latency

| Model | Expected Latency | Recommended Hardware |
|-------|-----------------|---------------------|
| Keyword filter | <1ms | Any |
| BERT toxicity | 50-200ms | CPU (4+ cores) or GPU |
| RoBERTa toxicity | 100-500ms | CPU (8+ cores) or GPU |
| NLI hallucination | 200ms-1s | CPU (8+ cores) or GPU |
| LLM judge (1B) | 1-5s | CPU (8+ cores) or GPU |
| LLM judge (7B+) | 5-30s | GPU recommended |

---

## Security Issues

### mTLS Connection Failures

```bash
# Verify certificates exist
ls -la nginx/certs/

# Regenerate certificates
make certs

# Check mTLS is enabled
grep MTLS_ENABLED .env
```

### FIPS Mode Issues

```bash
# Build FIPS-compliant image
make fips-build

# Verify FIPS is enabled
docker compose exec gateway python -c "
from services.shared.security.fips import is_fips_enabled
print('FIPS enabled:', is_fips_enabled())
"
```

### Vault Connection Failures

```bash
# Check Vault is running
docker compose ps vault

# Initialize Vault
make vault-init

# Verify Vault status
docker compose exec vault vault status
```

---

## Database Issues

### Connection Failures

```bash
# Check Postgres is running
make status | grep postgres

# Verify connection
docker compose exec postgres pg_isready -U polarisgate

# Check connection string in .env
grep DATABASE_URL .env
```

### Migration Issues

```bash
# Run migrations manually
make migrate

# Check migration status
docker compose exec postgres psql -U polarisgate -c "SELECT * FROM schema_migrations;"

# Reset database (⚠️ destroys data)
docker compose down -v postgres
docker compose up -d postgres
make migrate
```

### Data Retention

```bash
# Check data retention settings
grep DATA_RETENTION_DAYS .env

# Manually trigger cleanup
docker compose exec gateway python -m scripts/clean_data
```

---

## Networking Issues

### Cannot Reach Dashboard

```bash
# Check Nginx is running
make logs nginx

# Verify port mapping
docker compose port nginx 443

# Check firewall
sudo lsof -i :443
```

### Inter-Service Communication Failures

```bash
# Test from within the Docker network
docker compose exec gateway curl -s http://guardrails:8005/health

# Check DNS resolution
docker compose exec gateway getent hosts guardrails
```

---

## Debugging Tools

### View All Logs

```bash
# Follow all services
make logs

# Follow a specific service
make logs gateway

# View last N lines
docker compose logs --tail=100 gateway

# View logs with timestamps
docker compose logs -t gateway
```

### Interactive Debugging

```bash
# Shell into a running container
docker compose exec gateway /bin/bash

# Run Python in a service
docker compose exec guardrails python

# Execute a SQL query
docker compose exec postgres psql -U polarisgate -d polarisgate -c "SELECT * FROM audit_log LIMIT 10;"
```

### Network Diagnostics

```bash
# DNS resolution
docker compose exec gateway nslookup guardrails

# Connectivity test
docker compose exec gateway curl -v http://guardrails:8005/health

# Trace route (if traceroute is installed)
docker compose exec gateway traceroute guardrails
```

### Resource Monitoring

```bash
# CPU/Memory usage of Docker containers
make stats

# Detailed container resource usage
docker stats

# Disk usage
df -h

# Docker disk usage
docker system df
```

---

## Getting Help

If you can't resolve your issue:

1. **Search existing issues**: https://github.com/polarisgate/polarisgate/issues
2. **Open a new issue** with:
   - Version information
   - Deployment method (Docker Compose / K8s)
   - Full error logs
   - Steps to reproduce
3. **Contact support**: support@polarisgate.ai

> **Enterprise support plans** are available with guaranteed SLAs. Contact sales@polarisgate.ai for details.