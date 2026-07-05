# PolarisGate System Architecture

## Overview

PolarisGate is a **microservices-based AI governance platform** designed for enterprise-grade deployment. This document covers the system architecture, service interactions, data flows, and key design decisions.

## Architecture Principles

1. **Defense in Depth** — Multiple layers of security, safety, and compliance controls
2. **Modular Microservices** — Independently deployable, scalable services
3. **Policy as Code** — OPA-based Rego policies for all governance decisions
4. **Observability by Design** — Every service exposes metrics, traces, and logs
5. **Zero Trust** — mTLS between all services, no implicit trust

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Internet / Clients                              │
│                    (REST API, Web UI, MCP, Agent SDKs)                       │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                            [ Nginx Reverse Proxy ]
                         (TLS termination, WAF, rate-limit)
                                      │
                      ┌───────────────┴───────────────┐
                      │         Gateway Service         │
                      │  Auth · RBAC · Audit · Sanitize │
                      │  Rate Limit · DLP · Classify    │
                      └───────────┬───────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
    ┌─────┴─────┐          ┌─────┴─────┐          ┌─────┴─────┐
    │ Guardrails │          │Hallucination│          │    OPA    │
    │(Tox/PII)   │          │  Detector   │          │  Policies │
    └───────────┘          └─────────────┘          └───────────┘
          │                       │                       │
    ┌─────┴─────┐          ┌─────┴─────┐          ┌─────┴─────┐
    │  AIDA     │          │  Bias      │          │  Kill     │
    │  Bridge   │          │  Monitor   │          │  Switch   │
    └───────────┘          └───────────┘          └───────────┘
          │                       │                       │
    ┌─────┴─────┐          ┌─────┴─────┐          ┌─────┴─────┐
    │ Budget    │          │ Semantic   │          │ Sidecar   │
    │ Controller│          │ Cache      │          │ Proxy     │
    └───────────┘          └───────────┘          └───────────┘
          │                       │                       │
    ┌─────┴─────┐          ┌─────┴─────┐          ┌─────┴─────┐
    │ Closed-   │          │ Collector  │          │ Agent     │
    │ Loop      │          │ (Metrics)  │          │ Scanner   │
    └───────────┘          └───────────┘          └───────────┘
          │                       │
    ┌─────┴─────┐          ┌─────┴─────┐
    │ Retraining│          │  MLflow   │
    │ Pipeline  │          │ Registry  │
    └───────────┘          └───────────┘
```

## Service Descriptions

### Core Services

| Service | Port | Language | Purpose |
|---------|------|----------|---------|
| **Gateway** | 8000 | Python/FastAPI | API gateway, auth, routing |
| **Guardrails** | 8005 | Python/FastAPI | Toxicity, PII, bias detection |
| **Hallucination Detector** | 8008 | Python/FastAPI | Factual accuracy verification |
| **OPA** | 8181 | Rego | Policy enforcement engine |

### Compliance Services

| Service | Port | Language | Purpose |
|---------|------|----------|---------|
| **AIDA Bridge** | 8001 | Python/FastAPI | Canadian Bill C-27 compliance |
| **Bias Monitor** | 8011 | Python/FastAPI | Fairness scoring and bias detection |

### Agent Governance

| Service | Port | Language | Purpose |
|---------|------|----------|---------|
| **Kill Switch** | 10001 | Python/FastAPI | Emergency agent termination |
| **Budget Controller** | 8007 | Python/FastAPI | Agent spending limits |
| **Sidecar Proxy** | 10002 | Envoy | mTLS termination, agent interception |
| **Semantic Cache** | 8010 | Python/FastAPI | LLM response caching |
| **Agent Scanner** | 8012 | Python/FastAPI | K8s agent discovery |

### Infrastructure

| Service | Port | Language | Purpose |
|---------|------|----------|---------|
| **Internal CA** | 10003 | Python/FastAPI | Certificate issuance |
| **Cert Manager** | 10004 | Python/FastAPI | Certificate lifecycle |
| **Collector** | 8006 | Python/FastAPI | Metrics aggregation |
| **MLflow** | 5000 | Python | ML experiment tracking |

### Learning & Improvement

| Service | Port | Language | Purpose |
|---------|------|----------|---------|
| **Closed-Loop** | 8009 | Python/FastAPI | Continuous improvement |
| **Retraining** | 8013 | Python/FastAPI | Model retraining pipeline |

### Supporting Infrastructure

| Component | Port | Purpose |
|-----------|------|---------|
| **Nginx** | 80/443 | Reverse proxy, TLS, WAF |
| **PostgreSQL** | 5432 | Primary database |
| **Redis** | 6379 | Session cache, token blacklist |
| **Ollama** | 11434 | LLM inference |
| **Vault** | 8200 | Secrets management |

## Request Lifecycle

### Guardrails Check Request

```
Client → Nginx → Gateway → Guardrails → OPA → Database
  │         │        │          │         │       │
  │         │        ├── Auth ──┤         │       │
  │         │        ├── RBAC ──┤         │       │
  │         │        ├── Sanitize ────────┤       │
  │         │        ├── Rate Limit ──────┤       │
  │         │        │                    │       │
  │         │        └── Forward ──► Toxicity ──► │
  │         │                       + PII         │
  │         │                       + Sentiment   │
  │         │                            │        │
  │         │                    OPA Policy Check │
  │         │                            │        │
  │         │                    Audit Log ───────►│
  │         │                            │        │
  │         │◄─────── Response ──────────┤        │
  │◄────────┴──────── Response ──────────┤        │
```

### Hallucination Detection Request

```
Client → Gateway → Hallucination Detector (Cascade)
                       │
              ┌────────┴────────┐
              │  Tier 1:        │
              │  Prefilter      │
              │  (keyword)      │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │  Tier 2:        │
              │  NLI Detector   │
              │  (cross-encoder)│
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │  Tier 3:        │
              │  LLM Judge     │
              │  (Ollama)       │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │  Ensemble       │
              │  (weighted)     │
              └────────┬────────┘
                       │
              Response to Gateway
```

## Data Flow

### Security Data Flow

```
Client Request
  │
  ├── Nginx (TLS termination, WAF rules)
  │     │
  │     └── Gateway
  │           │
  │           ├── Auth (JWT validation or API key check)
  │           ├── RBAC (role-based permission check)
  │           ├── Sanitizer (XSS, SQLi, command injection)
  │           ├── Rate Limiter (token bucket)
  │           ├── DLP (content inspection)
  │           ├── Classification (data sensitivity)
  │           │
  │           └── Backend Service
  │                 │
  │                 └── Audit Chain (tamper-proof logging)
  │
  └── Response
```

### Monitoring Data Flow

```
Services → Prometheus (metrics scrape)
   │            │
   │            ├── Alertmanager (alerts)
   │            └── Grafana (dashboards)
   │
   └── OpenTelemetry (traces)
                │
                └── Jaeger/Tempo (tracing backend)
```

## Deployment Models

### Development (Docker Compose)

Single host, all services co-located. Ideal for testing and development.

```bash
make dev
```

### Staging (Docker Compose + Overrides)

Single host with production-like configuration.

```bash
make up
```

### Production (Kubernetes + Helm)

Multi-node cluster with auto-scaling, HA, and rolling updates.

```bash
helm install polarisgate k8s/helm/polarisgate
```

### Air-Gapped

Offline deployment without internet access.

```bash
make airgap-build
```

## Key Design Decisions

### Why OPA for Policy?

Open Policy Agent (OPA) provides:
- **Policy as Code** — Rego language for declarative policies
- **Decoupled** — Policies are separate from service logic
- **Fast** — Sub-millisecond evaluation
- **Auditable** — Every decision can be logged with its input

### Why Cascade Architecture for Hallucination Detection?

The cascade design provides:
- **Efficiency** — Fast prefilter catches obvious cases, expensive LLM only for ambiguous ones
- **Accuracy** — Multiple detectors with weighted ensemble
- **Configurable** — Depth and thresholds adjustable per use case
- **Graceful Degradation** — Higher tiers can be skipped if unavailable

### Why mTLS?

Mutual TLS ensures:
- **No Implicit Trust** — Every service proves its identity
- **Encryption** — All inter-service traffic is encrypted
- **Certificate Automation** — Internal CA auto-renews certificates
- **Compliance** — Required for HIPAA, PCI DSS, FedRAMP

## Scalability

### Horizontal Scaling

All services are stateless and can be horizontally scaled:
- **Gateway**: Scale by request volume
- **Guardrails**: Scale by check throughput (GPU recommended)
- **Hallucination Detector**: Scale by detection requests
- **OPA**: Scale by policy evaluation load

### Vertical Scaling

ML-heavy services benefit from vertical scaling:
- **Guardrails**: 8+ CPU cores, GPU for BERT/RoBERTa
- **Hallucination Detector**: 16+ CPU cores, GPU for LLM judge
- **Ollama**: GPU required for 7B+ models

## Performance Characteristics

| Service | P50 Latency | P99 Latency | Throughput |
|---------|-------------|-------------|------------|
| Gateway (auth) | 5ms | 20ms | 1000 req/s |
| Gateway (proxy) | 2ms | 10ms | 5000 req/s |
| Guardrails (keyword) | <1ms | 5ms | 10000 req/s |
| Guardrails (BERT) | 100ms | 500ms | 100 req/s |
| Guardrails (PII) | 10ms | 50ms | 500 req/s |
| Hallucination (prefilter) | 1ms | 10ms | 5000 req/s |
| Hallucination (NLI) | 500ms | 2s | 50 req/s |
| Hallucination (LLM) | 3s | 10s | 10 req/s |
| OPA | <1ms | 5ms | 10000 req/s |

## Security Architecture

See [Security Architecture](../security/architecture.md) for detailed security documentation.

## Compliance Architecture

See [Compliance](../compliance/) for detailed compliance documentation.

---

*Last updated: 2026-06-28*
*Maintainer: PolarisGate Architecture Team*