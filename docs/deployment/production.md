# Production Deployment Guide

This guide covers deploying PolarisGate in a production environment.

## Prerequisites

### Hardware Requirements

| Deployment Size | Services | CPU | RAM | Storage | GPU |
|----------------|----------|-----|-----|---------|-----|
| **Small** | Core services only | 8 cores | 16 GB | 100 GB | No |
| **Medium** | All services | 16 cores | 32 GB | 200 GB | Optional |
| **Large** | High throughput + ML | 32 cores | 64 GB | 500 GB | Required |
| **Enterprise** | HA + full ML | 64+ cores | 128+ GB | 1 TB+ | Required |

### Software Requirements

- Docker 24+ and Docker Compose v2 (or Kubernetes 1.28+)
- PostgreSQL 15+
- Redis 7+
- Python 3.11+
- OpenSSL 3.x (for FIPS mode)
- Helm 3+ (for Kubernetes deployments)

## Deployment Options

### Option 1: Docker Compose (Single Host)

Best for small to medium deployments with moderate throughput.

```bash
# 1. Clone and setup
git clone https://github.com/polarisgate/polarisgate.git
cd polarisgate
cp .env.example .env

# 2. Edit .env with production values
#    - Generate strong JWT_SECRET: openssl rand -hex 64
#    - Set strong database passwords
#    - Configure allowed CORS origins
#    - Set up monitoring endpoints

# 3. Build images
make build

# 4. Start services
make up

# 5. Verify health
make status
curl -s http://localhost:8000/health | jq .
```

### Option 2: Kubernetes (Production / HA)

Best for medium to large deployments requiring high availability and auto-scaling.

```bash
# 1. Add Helm repository
helm repo add polarisgate https://charts.polarisgate.ai

# 2. Install with custom values
helm install polarisgate polarisgate/polarisgate \
  --namespace polarisgate \
  --create-namespace \
  -f my-values.yaml
```

See [Kubernetes Deployment Guide](kubernetes.md) for detailed Helm chart configuration.

## Production Configuration

### Environment Variables

Override defaults in `.env`:

```bash
# Security
JWT_SECRET=<openssl rand -hex 64>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15  # Reduced for production
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql://polarisgate:<password>@postgres:5432/polarisgate
POSTGRES_PASSWORD=<strong-password>
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://:<password>@redis:6379/0
REDIS_PASSWORD=<strong-password>

# Encryption
ENCRYPTION_KEY=<openssl rand -hex 32>
FIPS_MODE=true

# Vault (recommended for production)
VAULT_ENABLED=true
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=<vault-token>

# mTLS
MTLS_ENABLED=true

# Monitoring
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus

# Rate Limiting
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=60

# Logging
LOG_LEVEL=info
JSON_LOGGING=true
```

### Production Checklist

- [ ] Generate strong secrets for JWT, database, Redis, encryption
- [ ] Enable mTLS (`MTLS_ENABLED=true`)
- [ ] Configure Vault for secrets management
- [ ] Set `FIPS_MODE=true` for regulated environments
- [ ] Configure breach notification endpoints
- [ ] Enable all required compliance frameworks
- [ ] Configure CORS origins to specific domains
- [ ] Set up Prometheus + Alertmanager
- [ ] Configure log aggregation (ELK/Loki/Grafana)
- [ ] Set up encrypted backups
- [ ] Run `make preflight-check`
- [ ] Run `make security-check`
- [ ] Use `Dockerfile.fips` for regulated deployments
- [ ] Configure resource limits in docker-compose.override.yml or Helm values
- [ ] Set up health check monitoring
- [ ] Configure alerting for service outages
- [ ] Test backup and restore procedures
- [ ] Document incident response procedures

## Scaling

### Horizontal Scaling (Kubernetes)

All services can be scaled horizontally:

```yaml
# values.yaml
gateway:
  replicas: 3
  resources:
    requests:
      cpu: "1"
      memory: "2Gi"
    limits:
      cpu: "2"
      memory: "4Gi"

guardrails:
  replicas: 3
  resources:
    requests:
      cpu: "2"
      memory: "4Gi"
    limits:
      cpu: "4"
      memory: "8Gi"

hallucination-detector:
  replicas: 2
  resources:
    requests:
      cpu: "4"
      memory: "8Gi"
    limits:
      cpu: "8"
      memory: "16Gi"
```

### Vertical Scaling

- **Guardrails**: Add GPU for BERT/RoBERTa inference (up to 10x throughput improvement)
- **Hallucination Detector**: Add GPU for LLM judge (up to 20x improvement for 7B+ models)
- **Ollama**: GPU required for models larger than 7B parameters
- **PostgreSQL**: Increase instance size and connection pool settings

## Monitoring

### Prometheus Metrics

All services expose metrics at `/metrics` on their internal ports.

Key metrics:
- `gateway_requests_total` — Total request count
- `gateway_request_duration_seconds` — Request latency
- `guardrails_checks_total` — Guardrails check count
- `guardrails_toxicity_score` — Toxicity scores
- `hallucination_detection_total` — Detection count
- `hallucination_score` — Hallucination scores
- `circuit_breaker_state` — Circuit breaker states
- `rate_limit_blocks_total` — Rate limit blocks

### Alerts

30+ alert rules are defined in `prometheus/alerts.yml`. Key alerts:

| Alert | Condition | Severity |
|-------|-----------|----------|
| GatewayDown | Service down >1m | Critical |
| HighErrorRate | Error rate >5% | Warning |
| APIHighLatency | P99 latency >1s | Warning |
| CircuitBreakerOpen | Any circuit breaker open | Critical |
| HighToxicityRate | Toxicity >10% of requests | Warning |
| HighHallucinationRate | Hallucination >5% of checks | Warning |
| LowDiskSpace | Disk usage >85% | Warning |
| CertificateExpiring | Cert expires <30 days | Warning |

See [Monitoring Guide](../monitoring/README.md) for detailed monitoring configuration.

## Security Hardening

### Network Security

- Deploy behind a Web Application Firewall (WAF)
- Use network policies to restrict pod-to-pod communication (Kubernetes)
- Enable DDoS protection at the load balancer level
- Restrict access to management ports

### Authentication

- Use Vault for secrets management
- Rotate JWT signing keys periodically
- Enable API key rotation
- Configure short token lifetimes (15-30 minutes)

### Data Protection

- Enable field-level encryption for PII
- Configure data retention policies
- Enable audit chain for compliance
- Enable DLP for content inspection

### Compliance

Enable compliance frameworks based on your requirements:

```bash
# In .env
COMPLIANCE_MODE=full
GDPR_ENABLED=true
HIPAA_ENABLED=false
PCI_ENABLED=false
```

## Backup & Disaster Recovery

### Database Backups

```bash
# Manual backup
make backup

# Automated backup (configure in crontab)
0 2 * * * cd /opt/polarisgate && make backup
```

### Disaster Recovery

1. Restore PostgreSQL from encrypted backup
2. Restore Vault from backup/snapshot
3. Re-deploy services using Helm or Docker Compose
4. Verify all services are healthy
5. Verify audit chain integrity

See [Operations Guide](operations.md) for detailed DR procedures.

## Upgrading

See [Upgrade/Migration Guide](../upgrade/migration.md) for version-specific upgrade procedures.

## Troubleshooting

See [Troubleshooting Guide](../troubleshooting.md) for common production issues.

---

*Last updated: 2026-06-28*
*Maintainer: PolarisGate DevOps Team*