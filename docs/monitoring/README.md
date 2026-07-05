# Monitoring & Observability Guide

This guide covers monitoring, alerting, and observability for PolarisGate deployments.

## Overview

PolarisGate uses a metrics-first observability stack:
- **Prometheus** — Metrics collection and alerting
- **OpenTelemetry** — Distributed tracing
- **Structured Logging** — JSON-formatted logs
- **Grafana** — Dashboards (optional, recommended)

## Prometheus Metrics

All services expose metrics at `/metrics` on their internal ports.

### Scrape Configuration

Prometheus is pre-configured with 14 scrape targets in `prometheus/prometheus.yml`.

### Key Metrics by Service

#### Gateway
| Metric | Type | Description |
|--------|------|-------------|
| `gateway_requests_total` | Counter | Total HTTP requests |
| `gateway_request_duration_seconds` | Histogram | Request latency |
| `gateway_requests_by_method` | Counter | Requests by HTTP method |
| `gateway_requests_by_endpoint` | Counter | Requests by endpoint |
| `gateway_errors_total` | Counter | Error responses |
| `rate_limit_blocks_total` | Counter | Rate limit blocks |

#### Guardrails
| Metric | Type | Description |
|--------|------|-------------|
| `guardrails_checks_total` | Counter | Total checks performed |
| `guardrails_toxicity_score` | Gauge | Toxicity scores |
| `guardrails_pii_detections_total` | Counter | PII detections |
| `guardrails_check_duration_seconds` | Histogram | Check latency |

#### Hallucination Detector
| Metric | Type | Description |
|--------|------|-------------|
| `hallucination_detection_total` | Counter | Total detections |
| `hallucination_score` | Gauge | Hallucination scores |
| `hallucination_cascade_depth` | Histogram | Cascade depth used |

#### System Health
| Metric | Type | Description |
|--------|------|-------------|
| `circuit_breaker_state` | Gauge | Circuit breaker states (0=closed, 1=open) |
| `circuit_breaker_failures_total` | Counter | Circuit breaker failures |
| `semantic_cache_hits_total` | Counter | Cache hits |
| `semantic_cache_misses_total` | Counter | Cache misses |
| `budget_remaining` | Gauge | Remaining budget per agent |

### Custom Metrics

Your application can emit custom metrics via the Prometheus client library:

```python
from prometheus_client import Counter, Histogram, Gauge

checks_total = Counter('app_checks_total', 'Total checks', ['type'])
check_duration = Histogram('app_check_duration_seconds', 'Check duration')
model_score = Gauge('app_model_score', 'Model score', ['model'])
```

## Alerting

30+ alert rules are defined in `prometheus/alerts.yml`.

### Critical Alerts

| Alert Name | Condition | Description |
|------------|-----------|-------------|
| `GatewayDown` | `up{job="gateway"} == 0` for 1m | Gateway service is down |
| `HighErrorRate` | `rate(gateway_errors_total[5m]) > 0.05` | Error rate exceeds 5% |
| `CircuitBreakerOpen` | `circuit_breaker_state > 0` | Circuit breaker is open |
| `HighToxicityRate` | `rate(guardrails_toxicity_score[5m]) > 0.3` | High toxicity detected |
| `HighHallucinationRate` | `rate(hallucination_score[5m]) > 0.3` | High hallucination rate |
| `ServiceDown` | `up == 0` for any service | Any monitored service is down |

### Warning Alerts

| Alert Name | Condition | Description |
|------------|-----------|-------------|
| `APIHighLatency` | P99 latency > 1s | API response times degrading |
| `LowDiskSpace` | Disk usage > 85% | Storage capacity warning |
| `HighMemoryUsage` | Memory usage > 85% | Memory pressure |
| `CertificateExpiring` | Cert expiry < 30 days | mTLS certificates expiring |
| `BudgetExhausted` | Budget remaining < 10% | Agent budget nearly exhausted |
| `HighCacheMissRate` | Cache miss rate > 80% | Poor cache utilization |

### Configuring Alertmanager

```yaml
# prometheus/alertmanager.yml
route:
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'pager'
    - match:
        severity: warning
      receiver: 'email'

receivers:
  - name: 'pager'
    pagerduty_configs:
      - routing_key: '<pagerduty-key>'
  - name: 'email'
    email_configs:
      - to: 'ops@polarisgate.ai'
        from: 'alerts@polarisgate.ai'
        smarthost: 'smtp.example.com:587'
```

## Distributed Tracing

### OpenTelemetry Integration

All Python services are instrumented with OpenTelemetry:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(
    endpoint="http://otel-collector:4318/v1/traces"
))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
```

### Tracing Configuration

Configure via environment variables:

```bash
OTEL_SERVICE_NAME=polarisgate-gateway
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1  # 10% sampling in production
```

### Compatible Backends

- **Jaeger** — Open source distributed tracing
- **Grafana Tempo** — Grafana's tracing backend
- **SigNoz** — Open source APM
- **Datadog** — Commercial APM

## Structured Logging

All services use structured JSON logging:

```json
{
  "timestamp": "2026-06-28T12:00:00.123Z",
  "level": "info",
  "service": "gateway",
  "request_id": "abc-123",
  "method": "POST",
  "path": "/api/v1/guardrails/check",
  "status": 200,
  "duration_ms": 45,
  "user": "admin",
  "trace_id": "def-456"
}
```

### Log Configuration

```bash
LOG_LEVEL=info
JSON_LOGGING=true
```

### Log Aggregation

Recommended stacks:
- **ELK** (Elasticsearch, Logstash, Kibana)
- **Loki** (Grafana Loki + Promtail)
- **Splunk** (commercial)

## Grafana Dashboards

### Quick Start

```bash
# Deploy Grafana
docker compose up -d grafana

# Default credentials: admin/admin
# Prometheus data source: http://prometheus:9090
```

### Importing Dashboards

Pre-built dashboards are available in `grafana/dashboards/`:

1. **PolarisGate Overview** — Service health, request rates, latency
2. **Guardrails Performance** — Toxicity/PII detection metrics
3. **Hallucination Detection** — Cascade performance
4. **Agent Governance** — Budget, cache, kill switch status
5. **Security & Compliance** — Audit, RBAC, compliance status

## Health Checks

All services expose `/health` endpoints:

```bash
# Check all services
for service in gateway guardrails hallucination-detector kill-switch; do
  status=$(curl -s -o /dev/null -w "%{http_code}" http://$service:8000/health)
  echo "$service: $status"
done
```

## Runbooks

### Service Down

1. Check Prometheus alert
2. Identify affected service
3. Check service logs: `docker compose logs <service> --tail=100`
4. Check resource utilization: `docker stats <service>`
5. Restart service: `docker compose restart <service>`
6. Verify recovery: `curl -s http://localhost:8000/health`

### High Error Rate

1. Check recent deploys/changes
2. Examine error logs for patterns
3. Check upstream dependencies (DB, Redis, Ollama)
4. Review rate limit configuration
5. Check for memory leaks or resource exhaustion

### Circuit Breaker Open

1. Identify failing downstream service
2. Check downstream service health
3. Investigate root cause from logs
4. Allow circuit breaker to reset (default: 60s)
5. If persistent, escalate to engineering team

---

*Last updated: 2026-06-28*
*Maintainer: PolarisGate DevOps Team*