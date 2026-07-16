# PolarisGate — Threat Model (STRIDE)

**Version:** 2.3  
**Date:** 2026-07-16  
**Framework:** STRIDE (Microsoft Threat Modeling) + OWASP ASVS v4.0  
**Scope:** PolarisGate API Gateway, Guardrails Service, Frontend SPA, PostgreSQL, Redis

---

## 1. System Overview

PolarisGate is a self-hosted AI content safety gateway that sits between an application and its LLM provider. It inspects every request (toxicity, PII, prompt injection) and every response (redaction, canary detection, blocklist filtering) in real time.

### Trust Boundaries

```
┌──────────────────────────────────────────────────────────────────┐
│                         INTERNET                                  │
│                            │                                      │
│              ┌─────────────▼─────────────┐                       │
│              │   Nginx Reverse Proxy     │  ← TLS 1.3, HSTS, CSP │
│              │   (port 80/443)           │                        │
│              └─────────────┬─────────────┘                       │
│                            │                                      │
│  ┌─────────────────────────┼──────────────────────────────┐     │
│  │              DOCKER NETWORK (trusted)                   │     │
│  │                                                         │     │
│  │  ┌──────────────┐   ┌──────────────┐   ┌───────────┐  │     │
│  │  │ Frontend SPA │   │ Gateway API  │   │ Guardrails│  │     │
│  │  │ (port 3000)  │◄─►│ (port 8000)  │◄─►│ (port 8005)│  │     │
│  │  └──────────────┘   └──────┬───────┘   └───────────┘  │     │
│  │                            │                            │     │
│  │                   ┌────────┼────────┐                   │     │
│  │                   ▼        ▼        ▼                   │     │
│  │              ┌─────────┐ ┌──────┐ ┌──────────────┐     │     │
│  │              │PostgreSQL│ │Redis │ │Hallucination │     │     │
│  │              │  (5432)  │ │(6379)│ │Detector(8008)│     │     │
│  │              └─────────┘ └──────┘ └──────────────┘     │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flows

| Flow | Protocol | Sensitivity |
|---|---|---|
| Browser → Nginx | HTTPS (TLS 1.3) | Auth tokens, credentials |
| Nginx → Gateway | HTTP (internal) | Auth tokens, prompt text |
| Gateway → Guardrails | HTTP (internal) | Prompt/response text |
| Gateway → PostgreSQL | TCP (internal) | Encrypted at rest: pgp_sym_encrypt |
| Gateway → Redis | TCP (internal) | Cache keys, rate limits |
| Gateway → Webhooks | HTTPS (external) | HMAC-signed payloads |

---

## 2. STRIDE Threat Analysis (Post-Fix)

### 🔴 Spoofing (S)

| Threat | Severity | Mitigation | Status |
|---|---|---|---|
| Brute-force login | High | 5 attempts/5min lockout per username, returns 429 | ✅ |
| JWT token forgery | Critical | JWT_SECRET >= 32 chars, HS256 algorithm | ✅ |
| Credential storage | High | bcrypt for passwords + API keys | ✅ |
| Multi-factor auth | High | **Not implemented** | ⚠️ Remaining gap |

### 🟠 Tampering (T)

| Threat | Severity | Mitigation | Status |
|---|---|---|---|
| CSRF on login | Medium | Double-submit cookie (SameSite=strict) on `/auth/token` | ✅ |
| Prompt payload tampering | Low | 32KB truncate, strip non-printable, NFKC normalize | ✅ |
| Webhook spoofing | Medium | HMAC-SHA256 signing (`whsec_*` auto-generated secrets) | ✅ |
| SQL injection | Critical | Parameterized queries throughout all routers | ✅ |
| Audit log tampering | Medium | HMAC chain integrity (chain_hash linking every entry) | ✅ |
| Response tampering | Medium | CSP headers (default-src 'self', object-src 'none') | ✅ |

### 🟡 Repudiation (R)

| Threat | Severity | Mitigation | Status |
|---|---|---|---|
| Deniable actions | Medium | Comprehensive audit trail with chain integrity | ✅ |
| Deleted audit entries | Medium | HMAC chain breaks at gap, detectable via `/audit/verify` | ✅ |
| Missing session tracking | Medium | Token families table + configurable session timeout (Settings) | ✅ |

### 🟢 Information Disclosure (I)

| Threat | Severity | Mitigation | Status |
|---|---|---|---|
| Token in localStorage (XSS) | High | Strict CSP (script-src 'self' 'unsafe-inline', no external scripts) | ⚠️ Accepted risk |
| Stack trace leakage | Low | Pydantic validation errors, no raw exception exposure | ✅ |
| Prompt exfiltration (zero-day) | Critical | Canary token detection in guardrails pipeline (stage 5) | ✅ |
| Sensitive data at rest | High | pgp_sym_encrypt for canary tokens, bcrypt for credentials | ✅ |
| PII in audit logs | Medium | PII auto-masked (email, phone, SSN, credit card patterns) | ✅ |

### 🔵 Denial of Service (D)

| Threat | Severity | Mitigation | Status |
|---|---|---|---|
| API flooding | Medium | slowapi 200/min + nginx 100r/s per-endpoint rate limiting | ✅ |
| Login brute-force | High | 5 attempts/5min → 429 response | ✅ |
| Massive prompt (OOM) | Medium | 32KB truncation in `sanitize_prompt()` | ✅ |
| DB connection exhaustion | Medium | Connection pooling with timeout | ✅ |
| ML inference loop | Medium | Circuit breaker with 30s timeout | ✅ |
| Session brute-force | Medium | Configurable session timeout (15min–4hr or Never) | ✅ |

### 🟣 Elevation of Privilege (E)

| Threat | Severity | Mitigation | Status |
|---|---|---|---|
| RBAC bypass | High | Three roles: Admin, Safety Officer, Viewer | ✅ |
| API key scope escalation | Medium | Scoped keys: read, write, admin | ✅ |
| Session hijacking | High | Configurable JWT expiry + CSRF cookie (SameSite=strict) | ✅ |
| Token reuse after logout | Medium | Token families table for cross-device revocation | ✅ |

---

## 3. Attack Trees

### Attack 1: Exfiltrate System Prompt via Injection

```
Attacker Goal: Steal system prompt and RAG context
│
├── Exploit prompt injection to leak system instructions
│   ├── [MITIGATED] 45 regex patterns (0.72–0.97 confidence)
│   ├── [MITIGATED] Semantic embeddings (384-dim all-MiniLM-L6-v2)
│   ├── [MITIGATED] SetFit custom ML classifier (96.7% recall)
│   └── [MITIGATED] Canary token detection catches the leaked prompt
│
├── Extract RAG context via adversarial queries
│   └── [PARTIAL] Canary token in RAG documents detects context exfiltration
│       Manual planting only — auto-injection planned for v2.4
│
├── Encode attack in non-English language
│   ├── [MITIGATED] French keywords (100% accuracy)
│   ├── [PARTIAL] Arabic keywords (50% precision, morphologically rich)
│   └── [PLANNED] Arabic SetFit pipeline to push precision to 90%+
│
└── Obfuscate with homoglyphs/leetspeak
    ├── [MITIGATED] Leetspeak normalization: h4t3→hate (67% recall)
    ├── [MITIGATED] Unicode normalization: 𝕙𝕒𝕥𝕖→hate
    └── [PARTIAL] Multi-layer obfuscation (leetspeak + homoglyphs) not covered
```

### Attack 2: Gain Admin Access

```
Attacker Goal: Log in as admin
│
├── Brute-force password
│   └── [MITIGATED] 5 attempts/5min window per username (auth.py:28-40)
│
├── Steal JWT via XSS
│   ├── [MITIGATED] CSP: script-src 'self', no third-party scripts
│   ├── [MITIGATED] X-Frame-Options: DENY
│   ├── [MITIGATED] CSRF cookie (SameSite=strict) on login
│   └── [PARTIAL] Token in localStorage accessible via JS (accepted risk)
│
├── SQL injection on login form
│   └── [MITIGATED] Parameterized queries throughout (e.g., `$1, $2, $3`)
│
├── Exploit SSRF to reach internal services
│   ├── [MITIGATED] Docker network isolation (internal_network)
│   └── [PARTIAL] No internal auth on inter-service calls (Docker network trust)
│
└── Steal API key from database dump
    ├── [MITIGATED] bcrypt-hashed in api_keys table
    └── [MITIGATED] Database not exposed externally (Docker internal network only)
```

### Attack 3: Denial of Service

```
Attacker Goal: Take down the gateway
│
├── Flood API with requests
│   ├── [MITIGATED] slowapi: 200 req/min default
│   ├── [MITIGATED] nginx: 100r/s API, 10r/s auth, 500r/s static
│   ├── [MITIGATED] Per-user rate limiting via Authorization header hash
│   └── [MITIGATED] 429 handler with rate limit exceeded response
│
├── Send massive prompt to exhaust memory
│   └── [MITIGATED] 32KB input truncation in sanitize_prompt() (guardrails.py:32)
│
├── Exhaust DB connection pool
│   ├── [MITIGATED] Connection pooling with timeout
│   └── [PARTIAL] No request timeout enforcement at application level
│
├── Trigger infinite ML inference
│   └── [MITIGATED] Circuit breaker with 30s timeout + keyword fallback
│
├── Exhaust Redis connections
│   └── [PARTIAL] Redis connection pooling, no explicit connection limit
│
└── Exploit recursive API calls
    └── [PARTIAL] No request depth/recursion limit
```

---

## 4. Risk Matrix

| Risk | Likelihood | Impact | Score | Status |
|---|---|---|---|---|
| Brute-force login | Low | High | **Medium** | ✅ Mitigated |
| JWT token forgery | Very Low | Critical | **Medium** | ✅ Mitigated |
| SQL injection | Very Low | Critical | **Medium** | ✅ Mitigated |
| Prompt injection data leak | Medium | High | **High** | ✅ Mitigated (6 gates) |
| Zero-day exfiltration | Low | Critical | **Medium** | ✅ Mitigated (canary tokens) |
| Token theft via XSS | Low | High | **Medium** | ⚠️ Accepted (CSP mitigates) |
| Webhook spoofing | Low | Medium | **Low** | ✅ Mitigated |
| Session hijacking | Low | High | **Low** | ✅ Mitigated |
| CSRF on login | Low | Medium | **Low** | ✅ Mitigated |
| Input-based DoS | Low | Medium | **Low** | ✅ Mitigated |
| Audit log tampering | Low | High | **Low** | ✅ Mitigated |
| ML model poisoning | Very Low | Critical | **Medium** | ⚠️ No model integrity checks |
| Malicious webhook payload | Low | Medium | **Low** | ✅ Mitigated (HMAC) |
| Rogue admin creates backdoor | Very Low | Critical | **Medium** | ✅ Mitigated (RBAC + audit trail) |

---

## 5. Residual Risks (Accepted)

| Risk | Rationale |
|---|---|
| **Token in localStorage** | SPA requires `Authorization: Bearer` header. Mitigated by strict CSP, no third-party scripts, X-Frame-Options: DENY. Migration to HttpOnly cookies planned for v3.0 |
| **No MFA** | Accepted for v2.3. TOTP integration planned for v2.4 |
| **No model integrity checks** | ML models loaded at startup from Docker image. Supply chain verification via container image signing planned |
| **Docker runs as root** | Accepted for development. Production Dockerfile (`Dockerfile.fips`) uses non-root user |
| **No request depth limit** | Accepted for v2.3. Depth limit middleware planned for v2.4 |
| **Arabic keyword precision (50%)** | Arabic morphological roots match clean text. SetFit pipeline infrastructure built, awaiting deployment |

---

## 6. Score Progression

| Metric | Initial (v2.0) | After 7 Fixes (v2.3) | Post-Log Integrity | Target (v3.0) |
|---|---|---|---|---|
| OWASP ASVS v4.0 | 6.4/10 | 8.8/10 | **9.0/10** | 9.5/10 |
| Authentication | 5.0 | 8.5 | 9.0 | 9.5 |
| Session Management | 5.0 | 9.0 | 9.5 | 9.5 |
| Access Control | 7.0 | 9.0 | 9.0 | 9.0 |
| Input Validation | 6.0 | 9.0 | 9.0 | 9.0 |
| API Security | 8.0 | 10.0 | 10.0 | 10.0 |
| Data Protection | 9.0 | 9.0 | 9.5 | 9.5 |
| Audit Integrity | 7.0 | 7.0 | 9.5 | 9.5 |

---

## 7. References

- OWASP ASVS v4.0 — https://owasp.org/www-project-application-security-verification-standard/
- OWASP LLM Top 10 — https://owasp.org/www-project-top-10-for-large-language-model-applications/
- NIST AI RMF 1.0 — https://www.nist.gov/itl/ai-risk-management-framework
- EU AI Act — https://artificialintelligenceact.eu/
- CLLMSE Handbook — Domain 5, §5.4 (Canary Token Detection)