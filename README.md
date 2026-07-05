<h1 align="center">PolarisGate</h1>
<p align="center">
  <em>AI Content Safety Gateway — Open-Source, Self-Hosted</em>
</p>

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-features">Features</a> •
  <a href="#-quickstart">Quickstart</a> •
  <a href="#-sdk">Python SDK</a> •
  <a href="#-testing">Testing</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-compliance">Compliance</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.2.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-purple.svg" alt="Python">
</p>

---

## Overview

PolarisGate is an **open-source, self-hosted AI content safety gateway** — a WAF for LLMs. It detects toxic content, PII, prompt injection attacks, and hallucination in LLM outputs, enforces configurable safety policies, and provides a complete audit trail. Built for teams that need enterprise-grade safety without cloud lock-in.

### Why PolarisGate?

| Need | PolarisGate Solution |
|------|---------------------|
| "I need to detect toxic content" | Multi-tier toxicity detection (keyword → BERT → LLM cascade) |
| "I need to redact PII, not just flag it" | Automatic PII redaction (email→`j***@***.com`, phone→`***-***-****`) |
| "I need prompt injection protection" | 45 regex-based injection patterns with confidence scores |
| "I need audit evidence" | Complete audit trail with user, action, resource, timestamp |
| "I can't send data to the cloud" | 100% self-hosted — Docker Compose in 2 minutes |
| "I can't afford enterprise pricing" | Free and open source (Apache 2.0) |

### Quick Comparison

| Feature | PolarisGate | Guardrails AI | NeMo | Lakera | Azure AI |
|---------|:---:|:---:|:---:|:---:|:---:|
| Toxicity Detection | ✅ | ✅ | ✅ | ✅ | ✅ |
| PII Detection | ✅ | ✅ | ✅ | ✅ | ✅ |
| **PII Redaction** | ✅ | ✅ | ❌ | ❌ | ❌ |
| Prompt Injection Detection | ✅ (45 patterns) | ❌ | ✅ | ✅ | ❌ |
| **Hallucination Detection** | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Dashboard / UI** | ✅ | ❌ | ❌ | ✅ | ✅ |
| **Audit Trail** | ✅ | ❌ | ❌ | ❌ | ❌ |
| Custom Policies | ✅ | ✅ | ✅ | ❌ | ❌ |
| Batch Testing | ✅ | ❌ | ❌ | ✅ | ❌ |
| Webhooks | ✅ | ❌ | ❌ | ✅ | ❌ |
| Self-Hosted | ✅ | ✅ | ✅ | ❌ | ❌ |
| Open Source | ✅ | ✅ | ✅ | ❌ | ❌ |
| Python SDK | ✅ | ✅ | ✅ | ✅ | ✅ |
| Streaming SSE | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Features

### Content Safety
- **Toxicity Detection** — Multi-tier: keyword matching → BERT classifier → LLM verification
- **PII Detection & Redaction** — SIN, SSN, email, phone, credit card, health card, IP, passport with automatic masking
- **Prompt Injection Detection** — 45 patterns including DAN, jailbreak, system override, bypass attempts
- **Hallucination Detection** — Dual-model NLI ensemble for factual accuracy checking
- **Custom Blocklists** — Add words/phrases to block specific content (competitor names, internal jargon)
- **Domain Thresholds** — Per-industry safety rules (finance, healthcare, education, general)

### Platform
- **Dashboard** — 7 summary cards (traces, toxicity, PII, blocked words, models, safety score, hallucination rate)
- **Incident Management** — Filterable incident list with Blocked/Toxic/PII/Clean verdict badges
- **Policy Engine** — 13 configurable safety policies with toggle switches and action/severity selectors
- **Content Testing** — Real-time content analysis with redacted output preview + batch testing
- **Audit Trail** — Complete record of safety decisions, policy changes, and user actions
- **API Keys** — Create, list, and revoke API keys for programmatic access
- **Webhooks** — Real-time notifications for safety incidents (Slack, Teams, custom)
- **Multi-Language UI** — English 🇬🇧, Français 🇫🇷, العربية 🇸🇦

### Security & Compliance
- **JWT Authentication** — bcrypt password hashing, token refresh, logout
- **RBAC** — Admin, Safety Officer, and Viewer roles
- **Rate Limiting** — Per-endpoint rate limiting
- **Audit Trail** — Immutable record of all safety decisions
- **Self-Hosted** — No data leaves your infrastructure

---

## Quickstart

### Prerequisites
- Docker & Docker Compose
- 8GB RAM (for Ollama models)

### 2-Minute Setup

```bash
# Clone
git clone https://github.com/polarisgate/polarisgate.git
cd polarisgate

# Configure
cp .env.example .env

# Start (12 services)
docker compose up -d

# Verify
curl http://localhost:8002/health
# {"status":"ok","database":"healthy","redis":"healthy"}
```

### Login

| URL | Purpose |
|-----|---------|
| `http://localhost:3001` | PolarisGate Dashboard |
| `http://localhost:8002` | Gateway API |

**Credentials:** `admin@polarisgate.ai` / `PolarisGateDemo2024!`

### First Use

1. Open `http://localhost:3001` in your browser
2. Login with the default credentials
3. Go to **Policies → Policy Rules** to configure safety rules
4. Go to **Policies → Test Content** to test your content
5. Go to **Settings → API Keys** to create API keys for programmatic access

### API Usage

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8002/auth/token \
  -d 'username=admin@polarisgate.ai&password=PolarisGateDemo2024!' \
  | jq -r '.access_token')

# Check content
curl -s -X POST http://localhost:8002/api/v1/guardrails/check \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"I hate you, you idiot!"}' | jq

# Response:
# {
#   "toxic": true,
#   "toxic_score": 0.85,
#   "reason": "Keyword match",
#   "pii_detected": false,
#   "injection_detected": false,
#   "blocklisted": false,
#   "redacted_text": "I hate you, you idiot!"
# }
```

---

## Python SDK

### Installation

```bash
pip install -e sdk/
```

### Usage

```python
from polarisgate import PolarisGate

pg = PolarisGate(api_key="pk-...")

# Single check
result = pg.check("I hate you, you idiot!")
print(result)  # CheckResult(toxic(0.85))
print(result.is_safe())  # False

# Batch check
results = pg.check_batch(["Hello world", "I hate you", "john@example.com"])
for r in results:
    print(r.is_safe())

# Redact PII
safe = pg.redact("My email is john@example.com")
# "My email is j***@***.com"

# Stream results (SSE)
for event in pg.check_stream("hello kill world"):
    print(event["token"], event["toxic"])

# Health check
print(pg.health())
```

### SDK Features

| Method | Description |
|--------|-------------|
| `pg.check(text)` | Full safety check (toxicity, PII, injection, blocklist) |
| `pg.check_batch(texts)` | Batch safety check for multiple texts |
| `pg.redact(text)` | Redact PII and return cleaned text |
| `pg.check_stream(text)` | Stream token-by-token safety results (SSE) |
| `pg.health()` | Check gateway health |

### CheckResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `toxic` | `bool` | Whether toxic content was detected |
| `toxic_score` | `float` | Confidence score (0.0-1.0) |
| `reason` | `str` | Why the content was flagged |
| `pii_detected` | `bool` | Whether PII was detected |
| `pii_types` | `list` | Types of PII found |
| `pii_masked` | `bool` | Whether PII was redacted |
| `redacted_text` | `str` | Text with PII redacted |
| `injection_detected` | `bool` | Whether prompt injection was detected |
| `injection_score` | `float` | Injection confidence score |
| `blocklisted` | `bool` | Whether blocklisted words were found |

---

## Testing

### Test Suite Overview

PolarisGate has **26 test files with ~100 tests** across 4 layers:

### Layer 1: Strategy Compliance (14 tests)
Enforces product strategy — no agent governance, no drift. Runs in 0.2s.

```bash
python3 -m pytest tests/test_strategy_compliance.py -v
```

### Layer 2: API Contract (20 tests)
Validates that API response schemas never change. Runs in 1-2s.

```bash
python3 -m pytest tests/test_api_contract.py -v
```

### Layer 3: API Integration (~45 tests)
Tests all features through the gateway API.

```bash
# Injection detection (20 tests — 45 patterns)
python3 -m pytest tests/test_injection_detection.py -v

# PII redaction (6 tests)
python3 -m pytest tests/test_pii_redaction.py -v

# Gateway v2.1 integration (17 tests — users, dashboard, streaming, batch, API keys, webhooks, blocklists)
python3 -m pytest tests/test_gateway_v2.py -v
```

### Layer 4: E2E / UI (29 tests)
Tests the complete pipeline from API injection to UI verification using Playwright.

```bash
# SPA UI tests (15 tests — login, navigation, forms)
python3 -m pytest tests/e2e/test_spa_ui.py -v

# Data pipeline tests (7 tests — seed → API verify → UI cross-check)
python3 -m pytest tests/e2e/test_data_pipeline.py -v

# Comprehensive E2E (7 tests — all 52 test vectors through full pipeline)
python3 -m pytest tests/e2e/test_comprehensive_e2e.py -v
```

### Running All Tests

```bash
# Full suite
python3 -m pytest tests/ -v --tb=short

# Fast gate (PR checks, < 5 seconds)
python3 -m pytest tests/test_strategy_compliance.py tests/test_api_contract.py -v

# Full gate (merge to main, < 2 minutes)
python3 -m pytest tests/ -v --tb=line
```

### Test Files Reference

| File | Tests | Category | Purpose |
|------|-------|----------|---------|
| `test_strategy_compliance.py` | 14 | Strategy | Enforces product identity |
| `test_api_contract.py` | 20 | Contract | Validates API response schemas |
| `test_injection_detection.py` | 20 | Integration | 45 injection patterns via API |
| `test_pii_redaction.py` | 6 | Integration | Email, phone, SIN, credit card redaction |
| `test_gateway_v2.py` | 17 | Integration | Users, dashboard, streaming, batch, API keys, webhooks, blocklists, errors |
| `test_guardrails_api.py` | — | Integration | Toxicity + PII check API |
| `test_pii_detector.py` | — | Integration | PII detection |
| `test_pii_detector_comprehensive.py` | — | Integration | All PII types |
| `test_toxicity_accuracy.py` | — | Integration | Toxicity classifier accuracy |
| `test_toxicity_ensemble.py` | — | Integration | Ensemble toxicity |
| `test_policy_engine.py` | — | Integration | Policy CRUD |
| `test_policy_engine_comprehensive.py` | — | Integration | Full policy coverage |
| `test_hallucination_accuracy.py` | — | Integration | Hallucination accuracy |
| `test_hallucination_cascade.py` | — | Integration | Cascade pipeline |
| `test_hallucination_ensemble.py` | — | Integration | Ensemble hallucination |
| `test_nli_detector_unit.py` | — | Unit | NLI detector |
| `test_bert_classifier_unit.py` | — | Unit | BERT toxicity classifier |
| `test_circuit_breaker_unit.py` | — | Unit | Service circuit breaker |
| `test_auth_unit.py` | — | Unit | JWT, bcrypt |
| `test_auth.py` | — | Integration | Login, setup, refresh, logout |
| `test_frontend_fixes.py` | — | Integration | Frontend fix tests |
| `e2e/test_spa_ui.py` | 15 | E2E | Login, dashboard, policies, compliance, settings |
| `e2e/test_data_pipeline.py` | 7 | E2E | Seed → API → UI cross-check |
| `e2e/test_comprehensive_e2e.py` | 7 | E2E | 52 test vectors through full pipeline |
| `integration/test_e2e.py` | — | E2E | End-to-end integration |
| `test_polarisgate_demo.py` | — | Demo | Demo data seeding |

### Test Data Files

| File | Content |
|------|---------|
| `test_data/comprehensive_test_vectors.json` | 52 test vectors (41 injection, 6 PII, 2 toxic, 3 clean) |
| `test_data/toxicity_test_set.json` | Toxicity test vectors |
| `test_data/hallucination_test_set.json` | Hallucination test vectors |

### Prerequisites for E2E Tests

```bash
pip install playwright
python3 -m playwright install chromium
```

---

## Code Architecture & Best Practices

### Backend Architecture

#### Gateway Pattern (Single Entry Point)

The FastAPI gateway (`services/gateway/app/main.py`, ~600 lines) is the single entry point for all client requests. This follows the **API Gateway pattern**:

```
Client → Gateway (port 8002) → Guardrails / Hallucination / Bias / AIDA
```

**Why:** Single authentication point, unified rate limiting, centralized audit logging, simpler client SDK. Microservices are internal-only — clients never call them directly.

#### Middleware Chain

```python
# Order matters — each middleware wraps the next
app.add_middleware(CORSMiddleware, ...)  # Cross-origin for SPA
app.add_middleware(RateLimiter, ...)      # Rate limiting per endpoint
app.add_middleware(OpenTelemetry, ...)    # Tracing for observability
```

**Why:** Middleware order follows the [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) — security controls (CORS, rate limiting) should execute before business logic.

#### Dependency Injection

```python
async def incidents(
    current_user: dict = Depends(get_current_user)  # Auto-validates JWT
):
```

**Why:** FastAPI's `Depends()` pattern is the Python equivalent of Spring's `@Autowired` — decouples auth logic from business logic, makes testing trivial (mock the dependency).

#### Data-Driven Endpoints

Every endpoint returns typed Pydantic models:

```python
@app.get("/api/v1/dashboard/summary", response_model=DashboardSummary)
```

**Why:** Pydantic models act as **contract tests** — if the API changes its response shape, all consumers (frontend, SDK, tests) break immediately at compile/startup time rather than silently in production.

#### Circuit Breaker Pattern

```python
result = await call_with_circuit_breaker(
    service_name="guardrails",
    method="POST",
    url=f"{GUARDRAILS_URL}/api/v1/check",
    ...
)
```

**Why:** Prevents cascading failures — if the guardrails service is down, the circuit breaker returns a fallback response instead of timing out all downstream calls.

#### File-Based Configuration with Advisory Locking

```python
with open(POLICY_FILE_PATH, "w") as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    try: yaml.safe_dump(payload.model_dump(), f)
    finally: fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

**Why:** YAML files are human-readable and git-friendly. Advisory locking prevents race conditions when multiple requests write simultaneously (no database migration needed for config changes).

### Frontend Architecture

#### Static SPA (No Framework)

The frontend is a **single `index.html` + `app.js` + `styles.css`** served by nginx. No React, no Next.js, no build step.

**Why:**
- **Zero dependencies** — no `node_modules`, no webpack, no JSX transpilation
- **Instant load** — nginx serves static files, no SSR/SSG/build
- **AI-friendly** — a single JS file is easier for AI to understand and modify than 200 component files
- **Cacheable** — static assets with hash-busting (`?v=5`) for cache invalidation

#### Module Pattern with Translation Layer

```javascript
// Global namespace with namespaced translations
const T = { en: {...}, fr: {...}, ar: {...} };
function t(key) { return (T[lang] && T[lang][key]) || (T.en[key] || key); }

// Single-page app routing
async function render() {
  if (state.tab === 'dashboard') {
    if (state.sub === 'overview') await renderDashboard();
    else if (state.sub === 'incidents') await renderIncidents();
    // ...
  }
}
```

**Why:** The module pattern (IIFE) avoids global namespace pollution. The translation layer (`T` object) enables i18n without external libraries. Single routing function keeps navigation predictable for both humans and AI.

#### CSS Architecture

- **Toggle switches:** CSS-only `.toggle` class (no JavaScript animation)
- **Design tokens:** Repeated values use existing selectors (no CSS variables to avoid browser compatibility)
- **Dark theme:** Consistent `#0B1120` background with `#4F8EF7` primary accent

### Security Architecture

#### Defense in Depth

| Layer | Mechanism | Standard |
|-------|-----------|----------|
| **Authentication** | JWT + bcrypt (12 rounds) | OWASP ASVS V2.1 |
| **Authorization** | RBAC (admin/safety_officer/viewer) | OWASP ASVS V4.1 |
| **Rate Limiting** | Per-endpoint limits (30-200/min) | OWASP ASVS V11.1 |
| **Input Validation** | Pydantic model validation on all inputs | OWASP ASVS V5.1 |
| **Output Encoding** | JSON responses (auto-escaped by FastAPI) | OWASP ASVS V5.3 |
| **CORS** | Whitelist-only origins | OWASP ASVS V14.3 |
| **Audit Trail** | Every action logged with user, timestamp, IP | SOC 2 CC6.1 |

#### Password Storage

```python
bcrypt.hashpw(password.encode(), bcrypt.gensalt())
```

**Why:** bcrypt with 12 salt rounds is the [NIST SP 800-63B](https://pages.nist.gov/800-63-3/sp800-63b.html) recommended algorithm for password hashing.

#### Token Management

```python
# Access token: 24-hour expiry (stateless, no DB lookup)
access_token = create_access_token({"sub": username})

# Refresh token: 7-day expiry (stored in DB, revocable)
refresh_token = create_refresh_token({"sub": username})
```

**Why:** Short-lived access tokens limit damage from token theft. Refresh tokens allow session extension without re-login. This is the [OAuth 2.0 Bearer Token](https://datatracker.ietf.org/doc/html/rfc6750) pattern.

### Testing Architecture

#### Test Pyramid

```
        ╱  E2E/UI  ╲        ← 10% (29 tests, Playwright browser)
       ╱──────────────╲
      ╱   Integration   ╲    ← 40% (45 tests, HTTP to gateway)
     ╱────────────────────╲
    ╱     Unit Tests       ╲← 50% (30 tests, pure functions)
   ╱──────────────────────────╲
```

**Why:** [Google's Testing Blog](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html) — E2E tests are slow and flaky. Keep them minimal. Unit tests are fast and reliable. Make them the foundation.

#### Strategy Compliance Tests

```python
def test_only_content_safety_endpoints():
    """Strategy: No agent governance, budget, drift, MLflow endpoints."""
    r = requests.get(f"{BASE}/openapi.json")
    paths = list(r.json().get("paths", {}).keys())
    FORBIDDEN = ["agent", "budget", "drift", "mlflow", "kill"]
    violations = [p for p in paths if any(f in p.lower() for f in FORBIDDEN)]
    assert len(violations) == 0, f"Forbidden endpoints: {violations}"
```

#### Contract Tests

```python
def test_guardrails_check_schema():
    result = check("hello world")
    REQUIRED = ["toxic", "pii_detected", "injection_detected", "blocklisted", ...]
    for field in REQUIRED:
        assert field in result, f"Missing field: {field}"
```

**Why:** Consumer-driven contracts ([Martin Fowler](https://martinfowler.com/articles/consumerDrivenContracts.html)). If the API response shape changes, the frontend and SDK break — contract tests catch this at CI time, not production.

#### Data-Driven Tests

```python
# 52 test vectors in a JSON file, one test function, many inputs
@pytest.mark.parametrize("vector", load_test_vectors())
def test_injection_patterns(vector):
    result = check(vector["text"])
    assert result["injection_detected"] == vector["expected"]
```

**Why:** [Data-driven testing](https://martinfowler.com/bliki/DataDrivenTesting.html) separates test logic from test data. Adding a new injection pattern requires only appending a JSON entry — no code change.

### CI/CD Integration

```bash
# Developer pushes code → AI might have generated it

# Stage 1: Strategy Gate (0.2s)
python3 -m pytest tests/test_strategy_compliance.py -v
# → Did AI add agents back? Did it change tab count? Did it add forbidden services?

# Stage 2: Contract Gate (1.5s)
python3 -m pytest tests/test_api_contract.py -v
# → Did AI change any API response shape?

# Stage 3: Integration Gate (10s)
python3 -m pytest tests/test_injection_detection.py tests/test_pii_redaction.py tests/test_gateway_v2.py -v
# → Do all features still work through the API?

# Stage 4: E2E Gate (30s)
python3 -m pytest tests/e2e/ -v
# → Does the UI still work end-to-end?

# All gates must pass before merge
```

### Design Decisions (TL;DR)

| Decision | Rationale |
|----------|-----------|
| **Static SPA, no React** | AI-friendly, no dependencies, instant load |
| **FastAPI (not Flask/Django)** | Native async, auto-generated OpenAPI docs, Pydantic integration |
| **YAML policies (not DB)** | Human-readable, git-friendly, advisory locking for safety |
| **BCrypt (not PBKDF2/Argon2)** | NIST-recommended, available in stdlib via `bcrypt` package |
| **Pydantic response models** | Contract enforcement — any schema change breaks at startup |
| **Strategy compliance tests** | AI-generated code gate — prevents product drift |
| **Data-driven test vectors** | Separate test logic from test data for easy expansion |
| **Circuit breaker pattern** | Prevents cascading failures in microservice architecture |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Internet                              │
└─────────────────────────────────────────────────────────┘
                         │
                [ Nginx Reverse Proxy ]
                         │
         ┌───────────────┴───────────────┐
         │      Gateway (FastAPI)         │
         │  Auth · RBAC · Audit · Sanitize │
         ├────────────────┬────────────────┤
         │  Guardrails    │  Hallucination │
         │ (Tox/PII/Inj)  │   Detector     │
         ├────────────────┴────────────────┤
         │  Bias Monitor · AIDA Bridge     │
         ├─────────────────────────────────┤
         │  Collector (Trace Ingestion)    │
         └─────────────────────────────────┘
                         │
     ┌───────────────────┼───────────────────┐
     │                   │                   │
[PostgreSQL]         [Redis]            [Ollama]
```

**12 Services:**
- `gateway` — FastAPI API (port 8002)
- `frontend` — Static SPA via nginx (port 3001)
- `guardrails` — Toxicity + PII detection (port 8005)
- `hallucination-detector` — NLI ensemble (port 8008)
- `bias-monitor` — Fairness scoring
- `aida-bridge` — Compliance bridge
- `collector` — Trace ingestion pipeline
- `postgres` — PostgreSQL 15 (AES-256-GCM)
- `redis` — Session cache
- `ollama` — LLM inference (Llama 3.2)
- `opa` — Policy engine (port 8181)
- `nginx` — Reverse proxy

---

## Compliance

PolarisGate is designed to help organizations meet compliance requirements:

| Standard | How PolarisGate Helps |
|----------|----------------------|
| **SOC 2** | Audit trail provides evidence of all safety decisions |
| **GDPR** | PII redaction prevents PII exposure in AI outputs |
| **HIPAA** | Custom blocklists + PII detection for PHI protection |
| **ISO 27001** | Access control via RBAC, JWT auth, API key management |
| **OWASP LLM Top 10** | Prompt injection detection (LLM01) |

For detailed compliance documentation, see [docs/compliance/](docs/compliance/).

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

## Competitive Analysis

PolarisGate is compared against 20 competitors in [competitive-analysis.md](competitive-analysis.md). Key findings:

- **Only 5 of 20** have PII redaction
- **Only 6 of 20** have hallucination detection
- **Only 3 of 20** have audit trails
- **Only 2 of 20** have batch testing + webhooks
- **Only 1 of 20** has all 15 features combined

---

## Support

- GitHub Issues: [github.com/polarisgate/polarisgate/issues](https://github.com/polarisgate/polarisgate/issues)
- Documentation: [docs/](docs/)
- SDK: [sdk/](sdk/)
