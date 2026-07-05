# PolarisGate Security Architecture

## Overview

PolarisGate implements a **defence-in-depth** security architecture designed for enterprise-grade AI governance platforms. The architecture spans network-layer controls, cryptographic protections, identity and access management, data protection, continuous monitoring, and compliance automation — aligned with SOC 2, FedRAMP, HIPAA, ISO 27001/42001, PCI DSS, GDPR, EU AI Act, and NIST AI RMF.

---

## 1. Network Security

### 1.1 Service Mesh & mTLS

All inter-service communication uses **mutual TLS (mTLS)** with X.509 certificates issued by an internal Certificate Authority (CA).

| Component | Description |
|-----------|-------------|
| `services/internal-ca/` | Internal CA service — issues, rotates, and revokes service certificates |
| `services/cert-manager/` | Certificate lifecycle management — monitors expiry, auto-renews |
| `services/shared/security/mtls.py` | mTLS wrapper — verifies peer certificates, enforces TLS 1.3 |

```
┌──────────────┐     mTLS (TLS 1.3)     ┌──────────────┐
│   Service A  │ ◄─────────────────────► │   Service B  │
│  (Client)    │   Client cert + CA pin   │  (Server)    │
└──────────────┘                         └──────────────┘
        │                                       │
        └──────────────► Internal CA ◄──────────┘
```

### 1.2 Reverse Proxy & WAF

Nginx operates as the **edge reverse proxy** with Web Application Firewall (WAF) rules:

- **Configuration:** `nginx/polarisgate.conf` (222 lines, enhanced WAF rules)
- Rate limiting per IP and endpoint
- Request size validation
- SQL injection and XSS pattern blocking
- Strict transport security (HSTS)
- Let's Encrypt auto-renewal

### 1.3 Network Policies

Kubernetes **NetworkPolicy** resources restrict pod-to-pod communication:

```
nginx → gateway:8000
gateway → guardrails:8005, aida-bridge:8001, collector:8006
guardrails → ollama:11434, redis:6379
gateway → postgres:5432 (via sidecar)
```

---

## 2. Identity & Access Management (IAM)

### 2.1 Authentication

| Module | File | Method |
|--------|------|--------|
| JWT Auth | `auth.py` | HS256 JWT with access/refresh token pair |
| API Keys | `api_keys.py` | HMAC-signed API key authentication |
| Session | `session.py` | Server-side session store in Redis |

**Token lifecycle:**
- Access token: 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- Refresh token: 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`)
- API keys: configurable, stored as bcrypt hashes

### 2.2 Authorization (RBAC)

| File | Roles | Granularity |
|------|-------|-------------|
| `rbac.py` | `admin`, `operator`, `auditor`, `developer`, `viewer` | Per-endpoint, per-method |

Permission model:
```python
permissions = {
    "admin":    {"gateway:*": True, "guardrails:*": True, "audit:*": True},
    "operator": {"gateway:read": True, "guardrails:read": True},
    "auditor":  {"audit:read": True, "compliance:read": True},
}
```

### 2.3 Input Sanitization

| File | Protections |
|------|-------------|
| `sanitizer.py` | XSS filtering, SQL escape, command injection prevention, path traversal blocking |


---

## 3. Cryptography

### 3.1 Encryption at Rest

| File | Algorithm | Key Management |
|------|-----------|----------------|
| `encryption.py` | AES-256-GCM | HKDF key derivation, auto key rotation with version tracking |

**Key hierarchy:**
```
Master Key (from Vault / env)
    └── HKDF-SHA256(salt, info="polarisgate-encryption-v1")
        └── Data Encryption Key (256-bit)
            └── AES-256-GCM nonce + ciphertext + auth_tag
```

### 3.2 Encryption in Transit

- **TLS 1.3** for all HTTP traffic
- **mTLS** for inter-service communication
- **PostgreSQL** SSL/TLS connections from gateway

### 3.3 FIPS 140-2/140-3 Compliance

| File | Capabilities |
|------|-------------|
| `fips.py` | FIPS-compliant hashing (SHA-256/384/512), signing (RSA 2048+), encryption (AES-256-GCM) |

When `FIPS_MODE=true`, all cryptographic operations use OpenSSL FIPS provider:
- AES-256-GCM (SP 800-38D)
- SHA-256/384/512 (FIPS 180-4)
- HMAC (FIPS 198-1)
- RSA with SHA-256 (FIPS 186-4)

---

## 4. Secrets Management

| File | Integration | Features |
|------|-------------|----------|
| `vault.py` | HashiCorp Vault (via `hvac`) | Dynamic secrets, auto-rotation, audit logging, KV v2 |

**Fallback chain:**
```
Vault (production) → Environment variables (staging) → Defaults (development)
```

---

## 5. Data Protection

### 5.1 Data Classification

| File | Classification Levels |
|------|----------------------|
| `data_classification.py` | `public`, `internal`, `confidential`, `restricted`, `critical` |

Classification rules are defined in `policies/pii_context.yaml` and evaluated via OPA.

### 5.2 Data Loss Prevention (DLP)

---

## 6. Audit & Observability

### 6.1 Tamper-Proof Audit Chain

| File | Mechanism |
|------|-----------|
| `audit.py` | SHA-256 hash chain with linked blocks |

Each audit event contains:
```json
{
  "event_id": "uuid",
  "timestamp": "ISO-8601",
  "service": "gateway",
  "action": "user.login",
  "actor": "user@example.com",
  "resource": "/api/v1/guardrails/check",
  "status": "success",
  "previous_hash": "sha256-of-previous-event",
  "current_hash": "sha256-of-this-event"
}
```

### 6.2 Telemetry & Tracing

| File | Stack |
|------|-------|

---

## 7. Incident Response

### 7.1 Breach Notification

| File | Capabilities |
|------|-------------|
| `breach_notification.py` | Automated 72-hour GDPR-compliant breach notification |

**Notification flow:**
1. Incident detected (DLP alert, anomaly, manual report)
2. Severity classification (HIGH: 24h, MEDIUM: 72h, LOW: 168h)
3. Escalation via email and/or webhook
4. Evidence collection and chain-of-custody logging
5. Post-incident reporting

### 7.2 Kill Switch

| Service | Location |
|---------|----------|
| `services/kill-switch/` | Emergency stop for agent execution |

**Activation triggers:**
- Hallucination rate above threshold
- Toxicity score exceeds limit
- Compliance violation detected
- Manual admin override

---

## 8. Compliance Automation

### 8.1 Compliance Manager

| File | Frameworks |
|------|------------|
| `compliance.py` | SOC 2, FedRAMP, HIPAA, ISO 27001, GDPR, PCI DSS, EU AI Act |

- Control mapping to multiple frameworks
- Automated evidence collection
- Compliance gap analysis
- Audit-ready reporting

### 8.2 GDPR Compliance

| File | Features |
|------|----------|
| `consent.py` | User consent management, right to erasure, data portability |

### 8.3 PCI DSS

| File | Features |
|------|----------|
| `pci.py` | Card data detection (Luhn), SAQ type D compliance, encryption scoping |

---

## 9. Container & Supply Chain Security

### 9.1 FIPS-Compliant Container Build

| Dockerfile | Base Image |
|------------|------------|
| `Dockerfile.fips` | `python:3.12-slim` + OpenSSL FIPS provider |

### 9.2 Pre-Commit Security Hooks

| File | Checks |
|------|--------|
| `.pre-commit-config.yaml` | `detect-secrets`, `ruff`, `mypy`, `bandit`, `trufflehog`, `semgrep` |

### 9.3 Static Analysis

| Tool | Config | Scope |
|------|--------|-------|
| Bandit | `.bandit.yaml` | Python security linter |
| Semgrep | `semgrep/rules/` | AI governance, command injection, secrets, open redirect, SSRF |

---

## 10. Rate Limiting

| File | Mechanism |
|------|-----------|
| `rate_limiter.py` | Token bucket algorithm with Prometheus metrics |

**Default limits (requests/minute):**
- General API: 100
- Auth endpoints: 30
- Guardrails check: 60

---

## 12. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Internet                                    │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                          [ Nginx Reverse Proxy + WAF ]
                          (rate-limit, HSTS, TLS 1.3)
                                    │
                    ┌───────────────┴───────────────┐
                    │         Gateway (FastAPI)       │
                    │  Auth · RBAC · Audit · Sanitize │
                    │  Vault · DLP · Classification   │
                    │  FIPS · Consent · Breach Notif. │
                    │  PCI · Rate Limit · Circuit Br. │
                    ├──────────┬──────────┬───────────┤
                    │Guardrails│ AIDA     │ Collector  │
                    │(Tox/PII) │ Bridge   │ (Metrics)  │
                    ├──────────┴──────────┴───────────┤
                    │ Hallucination Detector · Bias    │
                    │ Monitor · Budget Controller      │
                    ├─────────────────────────────────┤
                    │ Sidecar Proxy · Kill Switch      │
                    ├─────────────────────────────────┤
                    │ Semantic Cache · Closed-Loop     │
                    ├─────────────────────────────────┤

---

## 13. Security Compliance Mapping

| Control Area | SOC 2 | HIPAA | PCI DSS | GDPR | EU AI Act | FedRAMP |
|-------------|-------|-------|---------|------|-----------|---------|
| Access Control | CC6.1 | 164.312(a)(1) | 7.1.1 | Art. 5(1)(f) | Art. 15 | AC-2 |
| Encryption | CC6.7 | 164.312(a)(2)(iv) | 3.4 | Art. 32 | — | SC-13 |
| Audit Logging | CC3.1 | 164.312(b) | 10.2 | Art. 5(2) | Art. 12 | AU-2 |
| Risk Management | CC4.1 | 164.308(a)(1) | 12.2 | Art. 35 | Art. 9 | RA-3 |
| Incident Response | CC7.3 | 164.308(a)(6) | 12.10 | Art. 33-34 | Art. 62 | IR-4 |
| Data Classification | — | — | — | Art. 5(1)(c) | — | — |
| DLP | CC7.1 | 164.312(c)(1) | 3.4 | Art. 32 | — | SI-4 |

---

## 14. Configuration Reference

All security features are configurable via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `FIPS_MODE` | `false` | Enable FIPS 140-3 compliance |
| `MTLS_ENABLED` | `false` | Enable mTLS for inter-service |
| `VAULT_ENABLED` | `false` | Enable HashiCorp Vault |
| `DLP_ENABLED` | `true` | Enable DLP engine |
| `DLP_DEFAULT_ACTION` | `alert` | Action on DLP violation |
| `COMPLIANCE_MODE` | `full` | Compliance framework scope |
| `GDPR_ENABLED` | `true` | GDPR features |
| `HIPAA_ENABLED` | `false` | HIPAA features |
| `PCI_ENABLED` | `false` | PCI DSS features |
| `BREACH_NOTIFICATION_ENABLED` | `true` | Breach notification |
| `AUDIT_CHAIN_ENABLED` | `true` | Tamper-proof audit |
| `FIELD_LEVEL_ENCRYPTION` | `true` | PII field encryption |
| `SECURITY_MONITORING_ENABLED` | `true` | Real-time monitoring |

---

## 15. Deployment Considerations

### Production Checklist

1. **Enable mTLS** (`MTLS_ENABLED=true`)
2. **Configure Vault** with production-grade HA cluster
3. **Set `FIPS_MODE=true`** for government or regulated deployments
4. **Enable all compliance frameworks** relevant to jurisdiction
5. **Configure breach notification** email/webhook endpoints
6. **Deploy Prometheus + Alertmanager** for monitoring
7. **Set up log aggregation** (ELK/Loki/Grafana)
8. **Configure backup encryption** and offsite storage
9. **Run `make preflight-check`** before deploying
10. **Use `Dockerfile.fips`** for FIPS-compliant builds

### Air-Gapped Environments

Use `scripts/build_airgap.sh` to pre-fetch all dependencies for offline deployment.

---

*Last updated: 2026-06-27*
*Maintainer: PolarisGate Security Team*

                    │ OPA · MLflow · Retraining        │
                    └─────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   [PostgreSQL]               [Redis]                    [Ollama]
   (AES-256-GCM)          (Session cache)              (LLM inference)
        │                           │
   [Encrypted Backups]         [Vault]
```


**Prometheus metrics:** `rate_limit_requests_total`, `rate_limit_blocks_total`

---

## 11. Backup & Disaster Recovery

| Script | Details |
|--------|---------|
| `scripts/backup.sh` | Encrypted (AES-256-GCM) PostgreSQL backup (103 lines) |

**Backup schedule:** Daily with 30-day retention.


### 9.4 Dependency Scanning

| Script | Tools |
|--------|-------|
| `scripts/scan-deps.sh` | `pip-audit` + `safety` + `trivy` |

### 9.5 Air-Gapped Build

| Script | Purpose |
|--------|---------|
| `scripts/build_airgap.sh` | Offline build with pre-fetched dependencies |


### 8.4 OPA Policy Engine

OPA (Open Policy Agent) evaluates Rego policies for:
- EU AI Act articles (09, 13, 14, 15)
- Agent permission scoping
- Confidence threshold validation
- Cost allocation and budget limits

**Policy files:** `policies/eu_aia/`, `policies/agent_tools.rego`, `policies/cost.rego`


### 7.3 Circuit Breaker

| File | Details |
|------|---------|
| `circuit_breaker.py` | Compliance-aware circuit breaker (373 lines) |

**Failure classification:**
- **Transient** (timeouts, 502/503/504): count toward circuit trip
- **Permanent** (400, 401, 404): logged as bugs, do NOT trip

**Prometheus metrics:** `circuit_breaker_state`, `failure_counter`, `success_counter`

| `telemetry.py` | OpenTelemetry SDK with OTLP HTTP exporter |

- FastAPI auto-instrumentation for span creation
- Console exporter always enabled (debugging)
- OTLP exporter configurable via `OTEL_EXPORTER_OTLP_ENDPOINT`
- Compatible with Jaeger, Grafana Tempo, SigNoz

### 6.3 Prometheus Monitoring

| File | Details |
|------|---------|
| `prometheus/prometheus.yml` | 14 scrape targets across all services |
| `prometheus/alerts.yml` | 30+ alert rules (372 lines) |

**Alert categories:**
- Security incidents (breach, DLP violation, auth failure burst)
- Compliance drift (GDPR deadline, PCI scope change)
- Service health (high error rate, circuit breaker open)
- Resource exhaustion (OOM, OOMKilled, disk pressure)


| File | Detection Methods |
|------|-------------------|
| `dlp.py` | Regex patterns + ML classifiers |

**Sensitive data patterns detected:**
- PII: SSN, SIN, passport numbers, driver's license
- PHI: medical record numbers, health data
- PCI: credit card numbers (Luhn check)
- Credentials: API keys, tokens, passwords

**Actions:** `ALLOW`, `BLOCK`, `MASK`, `ALERT`, `QUARANTINE`

### 5.3 Field-Level Encryption

Field-level encryption for PII/PHI fields stored in PostgreSQL:
- Encrypted columns use `encrypt_pii()` / `decrypt_pii()` wrappers
- Each field gets a unique nonce (12 bytes)
- Encryption metadata stored alongside ciphertext (algorithm, version, timestamp)
