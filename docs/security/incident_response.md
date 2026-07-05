# PolarisGate Incident Response Plan

## Overview

This document defines the **Incident Response Plan (IRP)** for the PolarisGate AI governance platform. The plan aligns with SOC 2 (CC7.3), FedRAMP (IR-4), HIPAA (164.308(a)(6)), PCI DSS (12.10), GDPR (Articles 33-34), EU AI Act (Article 62), and NIST SP 800-61 Rev. 2.

---

## 1. Incident Classification

Incidents are classified by **severity** and **type**.

### 1.1 Severity Levels

| Level | Label | Response Time | Escalation | Examples |
|-------|-------|--------------|------------|----------|
| **P1** | Critical | ≤ 15 min | CISO + VP Eng | Data breach, unauthorized access, service-wide outage |
| **P2** | High | ≤ 1 hour | Security Lead + On-call Eng | DLP violation, prolonged degradation, compliance violation |
| **P3** | Medium | ≤ 4 hours | Security Team | Policy violation, isolated component failure, suspicious activity |
| **P4** | Low | ≤ 24 hours | Assigned Engineer | Minor anomaly, configuration drift, log warning |

### 1.2 Incident Types

| Type | Code | Description | Examples |
|------|------|-------------|---------|
| Security Breach | SEC-BR | Unauthorized access or data exposure | Credential leak, database compromise |
| DLP Violation | SEC-DLP | Sensitive data exfiltration or exposure | PII leak, credit card data transmission |
| Compliance Drift | SEC-CMP | Compliance framework violation | GDPR consent gap, PCI scope change |
| Availability | AVAIL | Service degradation or outage | Circuit breaker open, gateway unresponsive |
| AI Safety | AI-SAFE | Model hallucination or toxicity spike | Toxicity > 90%, hallucination rate > 15% |
| Attack | ATK | Active attack or intrusion | SQL injection, XSS, SSRF, DDoS |
| Insider Threat | INS | Malicious or negligent internal action | Privilege abuse, unauthorized data access |

---

## 2. Incident Response Team (IRT)

### 2.1 Team Structure

| Role | Responsibility | Primary | Backup |
|------|--------------|---------|--------|
| **Incident Commander** | Coordinates response, decisions | CISO | VP Engineering |
| **Security Lead** | Technical investigation | Security Engineer | Senior SRE |
| **Engineering Lead** | Service remediation | On-call SRE | DevOps Lead |
| **Compliance Officer** | Regulatory notification, evidence | Compliance Lead | Legal Counsel |
| **Communications Lead** | Stakeholder updates | Product Manager | CTO |

### 2.2 Contact Information

| Role | Contact Method | Target Response |
|------|---------------|-----------------|
| On-call Engineer | PagerDuty / Slack @on-call | 5 min |
| Security Team | security@polarisgate.ai | 15 min |
| CISO | ciso@polarisgate.ai | 15 min |
| Compliance | compliance@polarisgate.ai | 30 min |
| Legal | legal@polarisgate.ai | 1 hour |


---

## 3. Incident Response Lifecycle

The IRP follows the **NIST SP 800-61** four-phase model:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│Preparation│──►│Detection │──►│Containment│──►│Recovery  │
│& Planning │   │& Analysis│   │Eradication│   │Post-Mortem│
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### Phase 1: Preparation

| Activity | Owner | Frequency |
|----------|-------|-----------|
| Update incident response runbooks | Security Lead | Quarterly |
| Conduct tabletop exercises | Incident Commander | Quarterly |
| Review and update policies | Compliance Officer | Semi-annually |
| Maintain forensic tooling | Engineering Lead | Monthly |

**Tooling available:**
- `prometheus/alerts.yml` — 30+ automated security alerts
- `services/shared/security/audit.py` — Tamper-proof audit chain
- `services/shared/security/breach_notification.py` — Automated notification
- `scripts/backup.sh` — Encrypted backups for forensic recovery

### Phase 2: Detection & Analysis

#### 2.1 Automated Detection

PolarisGate automatically detects incidents via:

1. **Prometheus Alerts** — 30+ alert rules in `prometheus/alerts.yml`
2. **DLP Engine** (`dlp.py`) — Real-time content inspection
3. **Breach Notification** (`breach_notification.py`) — Automated severity classification
4. **Circuit Breaker** (`circuit_breaker.py`) — Service failure classification
5. **Kill Switch** (`services/kill-switch/`) — Emergency agent stop
6. **Audit Chain** (`audit.py`) — Anomaly detection via hash integrity checks

#### 2.2 Triage Process

| Step | Action | Responsible | Duration |
|------|--------|-------------|----------|
| 1 | Acknowledge alert/report | On-call Engineer | ≤ 5 min |
| 2 | Classify severity (P1-P4) | On-call Engineer | ≤ 10 min |
| 3 | Open incident in tracker | On-call Engineer | ≤ 15 min |
| 4 | Notify Incident Commander (P1/P2) | On-call Engineer | ≤ 15 min |
| 5 | Begin investigation | Security Lead | ≤ 30 min |

#### 2.3 Investigation Sources

| Source | Location | Purpose |
|--------|----------|---------|
| Audit chain | `services/shared/security/audit.py` | Immutable event log |
| Prometheus metrics | `prometheus/prometheus.yml` | Real-time service health |
| Structured logs | `shared/system_logs.py` | Correlation IDs across services |

### Phase 3: Containment, Eradication & Recovery

#### 3.1 Immediate Containment (P1/P2)

| Action | Tool/Mechanism | Owner |
|--------|---------------|-------|
| Revoke compromised credentials | Vault (`vault.py`) / RBAC (`rbac.py`) | Security Lead |
| Block malicious IP | Nginx WAF (`nginx/polarisgate.conf`) | Engineering Lead |
| Kill agent execution | Kill Switch (`services/kill-switch/`) | Engineering Lead |
| Enable circuit breaker | `circuit_breaker.py` | Engineering Lead |
| Scale down affected service | Kubernetes HPA / `scripts/autoscaler.sh` | Engineering Lead |
| Isolate compromised data | Encryption (`encryption.py`) / DLP (`dlp.py`) | Security Lead |

#### 3.2 Eradication

| Action | Method | Owner |
|--------|--------|-------|
| Remove persistent threats | Image rebuild, container recycle | Engineering Lead |
| Patch vulnerabilities | Dependency update (`scripts/scan-deps.sh`) | Engineering Lead |
| Rotate all secrets | Vault (`vault.py`) | Security Lead |
| Verify no remnants | Semgrep scan (`semgrep/rules/`) | Security Lead |

#### 3.3 Recovery

| Action | Validation | Owner |
|--------|-----------|-------|
| Restore from backup | `scripts/backup.sh` integrity check | Engineering Lead |
| Verify audit chain | `audit.py` integrity verification | Security Lead |
| Run compliance checks | `compliance.py` automated checks | Compliance Officer |
| Gradual traffic ramp | Nginx rate limiting, canary deploy | Engineering Lead |

### Phase 4: Post-Incident Activity

#### 4.1 Breach Notification (GDPR Article 33-34)

| Severity | Notification Deadline | Recipients |
|----------|---------------------|------------|
| HIGH | 24 hours | Supervisory authority + data subjects |
| MEDIUM | 72 hours | Supervisory authority |
| LOW | 168 hours (7 days) | Internal stakeholders |

**Notification method:** Configured via `.env.example`:
```
BREACH_NOTIFICATION_METHOD=email
BREACH_NOTIFICATION_EMAIL=security@northguard.ai
BREACH_NOTIFICATION_HIGH_HOURS=24
BREACH_NOTIFICATION_MEDIUM_HOURS=72
BREACH_NOTIFICATION_LOW_HOURS=168
```

#### 4.2 Post-Mortem Process

| Activity | Timeline | Deliverable |
|----------|----------|-------------|
| Timeline reconstruction | Within 48 hours | Incident timeline |
| Root cause analysis | Within 72 hours | RCA document |
| Remediation plan | Within 1 week | Action items with owners |
| Regulatory report (if applicable) | Per framework deadline | Compliance report |
| Post-mortem meeting | Within 1 week | Meeting notes |

**Post-mortem template includes:** Incident summary, timeline, root cause, detection gaps, response effectiveness, remediation actions, lessons learned.

#### 4.3 Evidence Retention

| Evidence Type | Retention | Storage |
|--------------|-----------|---------|
| Audit chain | 7 years (min) | Immutable audit database |
| Incident reports | 7 years (min) | Encrypted S3/compliance storage |
| Logs | 1 year | Log aggregation system |
| Forensics snapshots | 90 days | Encrypted cold storage |
| Post-mortems | 7 years (min) | Compliance documentation |

| Full system test | `make test` + `make test-aiml` | Engineering Lead |


---

## 4. Incident Response Automation

### 4.1 Automated Playbooks

| Trigger | Automated Response | File |
|---------|-------------------|------|
| DLP violation | Block/mask content, alert security team | `dlp.py` |
| Auth failure burst | Rate limit IP, log to audit chain | `auth.py` |
| Circuit breaker open | Alert Prometheus, scale redundant services | `circuit_breaker.py` |
| High hallucination rate | Activate kill switch, fallback to safe model | `services/kill-switch/` |
| Certificate expiry | Auto-renew via cert-manager | `services/cert-manager/` |
| Backup failure | Alert on-call, retry with backoff | `scripts/backup.sh` |

---

## 5. Communication Plan

### 5.1 Internal Communication

| Channel | Purpose | Frequency During Incident |
|---------|---------|--------------------------|
| `#security-incidents` | Real-time updates | Every 30 min (P1), hourly (P2) |
| `#eng-oncall` | Technical coordination | As needed |
| War room (Zoom/Meet) | Command center | Active during P1/P2 |
| Email | Formal updates | Status at milestones |

### 5.2 External Communication

| Stakeholder | Contact | Trigger |
|-------------|---------|---------|
| Customers | Status page + email | P1/P2 incidents affecting SLA |
| Regulators | Compliance Officer | GDPR 72h, PCI DSS, EU AI Act |
| Partners | Account manager | P1 incidents affecting integrations |
| Public | Blog post/PR | Major breach (CISO + Legal approval) |

---

## 6. Testing & Drills

### 6.1 Tabletop Exercises

| Scenario | Frequency | Participants |
|----------|-----------|-------------|

---

## 7. Continuous Improvement

### Key Metrics (measured quarterly)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Mean Time to Detect (MTTD) | < 15 min (P1), < 1 hour (P2) | Alert-to-triage time |
| Mean Time to Respond (MTTR) | < 1 hour (P1), < 4 hours (P2) | Triage-to-containment |
| Mean Time to Resolve (MTTR) | < 4 hours (P1), < 24 hours (P2) | Containment-to-recovery |
| Post-mortem completion | 100% within 1 week | Documented RCA |
| Recurrence rate | < 5% | Incidents with same root cause |

---

## 8. Regulatory Compliance Mapping

| Framework | Key Requirements | PolarisGate Implementation |
|-----------|-----------------|---------------------------|
| **GDPR** Art. 33-34 | 72h breach notification | `breach_notification.py` |
| **SOC 2** CC7.3 | Incident response plan | This document |
| **PCI DSS** 12.10 | Incident response program | This document + `pci.py` |
| **HIPAA** 164.308(a)(6) | Security incident procedures | `breach_notification.py` |
| **EU AI Act** Art. 62 | Serious incident reporting | `services/kill-switch/` + alerts |
| **FedRAMP** IR-4 | Incident handling | This document + `audit.py` |
| **NIST SP 800-61** | Incident handling guide | This document (aligned) |

---

## Appendices

### A. Incident Report Template

```
# Incident Report

**Incident ID:** IR-YYYY-MM-NNN
**Severity:** P1/P2/P3/P4
**Type:** SEC-BR / SEC-DLP / SEC-CMP / AVAIL / AI-SAFE / ATK / INS
**Date:** YYYY-MM-DD
**Reported by:**
**Incident Commander:**

## Summary

## Timeline

| Time (UTC) | Event | Action Taken |
|------------|-------|--------------|

## Root Cause

## Impact

## Containment

## Recovery

## Lessons Learned

## Remediation Actions

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
```

### B. Key Contacts Quick Reference

| Role | Contact |
|------|---------|
| Incident Commander | — |
| Security Lead | security@polarisgate.ai |
| Engineering Lead | — |
| Compliance Officer | compliance@polarisgate.ai |
| Legal Counsel | legal@polarisgate.ai |

### C. Tool Quick Reference

| Tool | Purpose | Access |
|------|---------|--------|
| Prometheus | Metrics & alerting | `prometheus.polarisgate.internal` |
| Grafana | Dashboards | `grafana.polarisgate.internal` |
| PagerDuty | On-call escalation | PolarisGate account |
| Slack | Communication | `#security-incidents` |
| Jira | Incident tracking | PolarisGate IR project |
| Vault | Secrets management | `vault.polarisgate.internal` |
| Audit chain | Immutable audit log | API: `GET /api/v1/audit/chain` |

---

*Last updated: 2026-06-27*
*Maintainer: PolarisGate Security Team*
*Review cycle: Quarterly*
