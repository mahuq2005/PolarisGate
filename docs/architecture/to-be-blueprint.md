# PolarisGate — To-Be Architecture Blueprint

**Document Version:** 1.0
**Status:** Validated (security / ML / product review)
**Scope:** Target architecture for the enterprise AI adoption platform

---

## 1. Positioning & The Moat

### The Problem

Organizations want to adopt AI but cannot get InfoSec / Legal / Risk sign-off without proving safety, compliance, budget control, and auditability — **without sending data to a third party**.

### The Positioning

> **Secure and controlled enterprise AI adoption — self-hosted OR in your cloud (BYOA), with Canadian PII redaction, hallucination detection, and on-prem/air-gap capability as the uncopyable spears.**

### The Two Halves

```
SECURE     = safety (injection · PII · toxicity · hallucination) + data sovereignty (BYOA / on-prem)
CONTROLLED = governance (RBAC · policy · budgets · audit · agent control) + provider routing
```

### The Moat Is The Integration

No competitor bundles both halves, self-hosted:

| Competitor | Gap They Leave |
|---|---|
| LiteLLM | Routing/budget, weak safety, weak governance, cloud-oriented |
| Bedrock Guardrails | Safety, but AWS-only, no multi-provider, no on-prem, no governance |
| Onyx | Agent governance, but SaaS-only, no PII redaction / hallucination |
| Credo AI | Governance, but post-hoc (no runtime blocking), SaaS |
| **PolarisGate** | **Safety + governance + budget + audit + self-hosted, one deployable** |

### The Uncopyable Spears

- **Canadian PII recognizers** (SIN, health card, SWIFT/CUSIP/ISIN) — Comprehend is US-centric; nobody else has these.
- **On-prem / air-gap** — Lakera/Onyx/Credo are SaaS; they cannot ship on-prem.
- **Self-hosted hallucination NLI** — rare; Bedrock's equivalent is cloud-only.

> **Rule:** the moat is NOT the ML. It is orchestration + Canadian PII + the provider-agnostic interface + BYOA + the governance/budget control plane.

---

## 2. Architecture Principles

1. **Capability-level registry** — each safety check (injection / PII / toxicity / hallucination) is an independently routable provider, so best-of-breed tools mix per-feature.
2. **Buy commodity, build differentiators** — buy injection ML (Prompt-Guard / Lakera), build Canadian PII + orchestration.
3. **One codebase, N deploy targets** — interface + factory + env var (on-prem + customer's cloud).
4. **Local-first, cloud-escalate** — default local models, optional managed per-feature.
5. **BYOA (Bring Your Own Account)** — deploy into the customer's cloud account; vendor has zero data access.
6. **Three pillars, one request path** — Safety, Budget, Governance intercept the same request.

---

## 3. Component Diagram (Hybrid Topology)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                     GATEWAY (FastAPI) — lightweight, I/O-bound             │
│                                                                            │
│   REQUEST PATH:                                                            │
│   Auth → Tenant → RBAC → SAFETY → BUDGET → LLM → BUDGET → SAFETY → Audit  │
│                                                                            │
│  ┌────────────────────┐ ┌─────────────────┐ ┌─────────────────────────────┐ │
│  │ PILLAR 1: SAFETY   │ │ PILLAR 2: BUDGET│ │ PILLAR 3: GOVERNANCE        │ │
│  │ (capability registry)│ │ (threshold gate)│ │ (control plane)             │ │
│  │                    │ │                 │ │                             │ │
│  │ injection ──► prov │ │ team_budgets    │ │ Policy Engine               │ │
│  │ pii ────────► prov │ │ quota_enforcer  │ │ RBAC                        │ │
│  │ toxicity ───► prov │ │ token_counter   │ │ Audit Trail                 │ │
│  │ hallucinate► prov │ │ budget_alerts   │ │ Agent/MCP gov.              │ │
│  │ bias (off) ─► slot│ │ anomaly_detector│ │ RAG                         │ │
│  └─────────┬──────────┘ └─────────────────┘ └─────────────────────────────┘ │
└────────────┼───────────────────────────────────────────────────────────────┘
             │ LocalSafetyProvider → HTTP (hybrid, no collapse)
   ┌─────────┼──────────────────────────────────────────────────────────┐
   │  ML SERVICES (stay separate — keep gateway light)                   │
   │  guardrails (BERT + Presidio + Canada recognizers)  :8005           │
   │  hallucination-detector (DeBERTa NLI)               :8008           │
   │  (cloud mode: replaced by Comprehend/Bedrock — services not deployed)│
   └─────────────────────────────────────────────────────────────────────┘
         │                                                    │
    ┌────▼─────────┐                                ┌─────────▼────────┐
    │  ON-PREM     │                                │  CLOUD (BYOA)    │
    │  Docker/Helm │                                │  Marketplace     │
    └──────────────┘                                └──────────────────┘
```

> **Topology decision (hybrid, not collapse):** the gateway container deliberately has no `torch`/`transformers`/`presidio` — collapsing ML into the gateway would balloon it to ~2–3 GB and slow startup. `LocalSafetyProvider` calls the ML services over HTTP behind the interface. Cloud mode swaps the HTTP calls for managed AI (Comprehend / Bedrock) and drops the ML services entirely.

---

## 4. Pillar 1 — Safety (Capability Registry + Injection Cascade)

### Config

```yaml
safety:
  injection:
    cascade: [regex, prompt_guard]   # layer 1 → layer 2; layer 3 = lakera (premium)
    threshold: 0.5
  pii:          { provider: presidio_ca, redaction: true }   # moat
  toxicity:     { provider: bert }
  hallucination:{ provider: deberta_nli }
  bias:         { enabled: false }   # demoted: slot retained, offline eval for EU AI Act / NIST
```

### Injection = Defense-in-Depth Cascade

```
Layer 1: regex patterns        → cheap, zero FP, catches known signatures (kept, not removed)
Layer 2: Prompt-Guard-86M      → local ML classifier — or Lakera (cloud, best accuracy)
Layer 3: LLM judge             → optional, high-confidence edge cases
```

**Named v1 requirement — indirect injection:** prompts embedded in retrieved docs/emails are the agent-era attack with the weakest single-model detection (Prompt-Guard ~71% TPR). Address explicitly — Lakera or a fine-tuned mDeBERTa is the enterprise path.

**License isolation:** Prompt-Guard (Llama 3.1 license) must be an *optional, separately-licensed dependency* — never baked into the Apache-2.0 core.

### Interface (per-capability, not monolithic)

```python
class InjectionProvider(ABC):
    capability = SafetyProviderType.INJECTION
    async def detect_injection(self, text, context=None) -> InjectionResult: ...

class PIIProvider(ABC):
    capability = SafetyProviderType.PII
    async def detect_pii(self, text, context=None) -> PIIResult: ...
    async def redact_pii(self, text, context=None) -> PIIResult: ...

class ToxicityProvider(ABC):
    capability = SafetyProviderType.TOXICITY
    async def detect_toxicity(self, text, context=None) -> ToxicityResult: ...

class HallucinationProvider(ABC):
    capability = SafetyProviderType.HALLUCINATION
    async def detect_hallucination(self, claim, source=None) -> HallucinationResult: ...

class BiasProvider(ABC):          # slot only — disabled by default
    capability = SafetyProviderType.BIAS
    async def check_bias(self, text, context=None) -> BiasResult: ...
```

### Provider Map

| Capability | Local (on-prem) | Cloud (AWS) | Premium |
|---|---|---|---|
| injection | regex + Prompt-Guard | Bedrock Guardrails | **Lakera** |
| pii | **Presidio + Canada** | Comprehend | — |
| toxicity | BERT | Comprehend | Azure AI |
| hallucination | DeBERTa NLI | Bedrock Claude NLI | — |
| bias | (off) | (off) | future |

---

## 5. Pillar 2 — Budget (Threshold Gate)

### The Loop (kept deliberately simple)

```
Request (team_id from TenantContextMiddleware — already wired)
   ▼
[PRE-CALL] check_quota(team_id)  → 403 if over budget + hard_cutoff
   ▼
[LLM CALL] provider.chat(req) → ProviderResponse.usage
   ▼
[POST-CALL] record_usage(team_id, provider, model, input_tokens, output_tokens, cost)
   ▼
[ASYNC] budget_alerts (80/90/100%) → webhook (Slack/Teams)
        anomaly_detector (z-score on usage_logs, >3σ = flag)
```

**Design:** hard cutoff only (block once over budget). No per-call cost prediction. Enterprises accept "block when exceeded" as v1.

### Data Model (already exists)

```
team_budgets: team_name, monthly_budget_usd, current_spend_usd, alert_threshold_pct, hard_cutoff, webhook_url
usage_logs:   user_id, team_id, provider, model, input_tokens, output_tokens, total_tokens, cost_usd
```

**Budget model = per-team (not per-user).** Enterprises budget by cost-center.

### Code Touch Points

| # | Where | What |
|---|---|---|
| 1 | `safety/pipeline.py` `run_full_pipeline()` | `check_quota(team_id)` before `provider.chat()`; `record_usage()` after |
| 2 | `quota_enforcer.py` | already correct |
| 3 | `token_counter.py` | already correct |
| 4 | `budgets.py` | already correct |
| 5 | `cost_tracker.py` (legacy in-memory) | **retire** — overlaps with the DB-backed system |

---

## 6. Pillar 3 — Governance (Control Plane)

| Component | Status |
|---|---|
| Policy Engine (13 YAML policies) | built |
| RBAC (admin / safety_officer / viewer + operator / auditor) | built |
| Audit Trail (immutable, chain-hashed) | built |
| Agent/MCP governance (tool access + policy) | partial — agent identity layer pending |
| RAG pipeline | scaffold |

---

## 7. End-to-End Request Flow

```
POST /api/v1/chat/completions
  1. Auth (JWT)
  2. Tenant middleware → team_id
  3. RBAC
  4. SAFETY input  → injection cascade → PII(redact) → toxicity
  5. BUDGET pre    → check_quota(team_id)
  6. LLM call
  7. BUDGET post   → record_usage
  8. SAFETY output → hallucination → PII → toxicity
  9. Audit log
  10. Return response + safety verdicts + budget status
```

---

## 8. Phase Roadmap

| Phase | Work | Outcome |
|---|---|---|
| **P0 — Interface wiring (1 wk)** | `LocalSafetyProvider` → HTTP calls to guardrails/hallucination (hybrid); `pipeline.py` calls `app.state.safety_provider`; injection becomes a cascade | Interface real, regex kept as layer 1, gateway stays light |
| **P1 — Capability registry (1 wk)** | Monolithic → per-capability ABC + YAML + factory routing | Mix providers per-feature |
| **P2 — Budget loop (3–4 days)** | Wire `check_quota` + `record_usage`; retire legacy `cost_tracker.py` | Budgets have teeth |
| **P3 — Cloud providers (2–3 wk)** | AWS capability providers (Comprehend, Bedrock Guardrails, Bedrock Claude) + Terraform + PrivateLink | AWS Marketplace-ready |
| **P4 — Azure + GCP (2 wk)** | Same pattern | 3 clouds |
| **P5 — Governance completion** | Agent identity, RAG | Full platform |

> **Dev-machine note (not a product deliverable):** Ollama-in-Docker is slow on Apple Silicon only; Linux+GPU on-prem is fine. Do not treat "fix Ollama" as roadmap work.

---

## 9. Decisions & Rationale

| Decision | Why |
|---|---|
| **Hybrid topology** (LocalSafetyProvider → HTTP, not collapse) | Gateway stays lightweight; ML services keep their models; cloud mode drops ML services cleanly |
| **Injection cascade, not swap** | Single-model injection defense is a single point of failure; regex gives zero-FP layer 1 |
| **Capability registry over monolith** | Best-in-class tools are point solutions (Lakera = injection only, Comprehend = PII+toxicity); per-feature routing lets them mix |
| **Threshold budget, no cost prediction** | Simple "block when exceeded" is what enterprises accept as v1 |
| **Bias demoted, not dropped** | EU AI Act + NIST AI RMF name bias as a requirement; keyword stub is too crude to ship, so keep the slot + offline eval |
| **Buy injection ML, build PII** | Injection is commoditized (Prompt-Guard/Lakera); Canadian PII is the uncopyable moat |
| **Prompt-Guard license-isolated** | Llama 3.1 license inside an Apache-2.0 product must be an optional dependency |

---

## 10. Implementation Gaps Discovered In Code Review (P0/P1/P2 Prerequisites)

These were found by tracing the actual code paths. They MUST be resolved in or before P0/P1/P2.

### Gap 1 - Inter-Service Auth Does Not Exist (Blocks P0)

The guardrails service /api/v1/check is protected by require_auth (JWT). The gateway's current run_input_guardrails does inline regex - it does NOT call guardrails over HTTP. There is no shared service-token / inter-service auth helper. Decision needed: shared service token (X-Service-Token env-var) vs gateway-minted JWT. Recommendation: shared service token.

### Gap 2 - PII Redaction Has No ML Backend (Threatens The #1 Moat)

guardrails exposes detection only (scan/check). The Rewriter object exists (regex mask_pii) but no HTTP endpoint returns redacted text. LocalSafetyProvider.redact_pii uses gateway-local regex. Recommendation: expose /api/v1/redact on guardrails using Presidio anonymizer.

### Gap 3 - health_check() Lies (Silent Failure Risk)

LocalSafetyProvider.health_check() hardcodes status ok. After P0 it must probe guardrails :8005 + hallucination :8008 and report real availability.

### Gap 4 - Streaming Path Bypasses Budget + Interface

chat.py and proxy.py streaming routes call run_input_guardrails + provider.chat_stream() directly - no check_quota / record_usage. All paths must go through the same interface + budget loop.

### Gap 5 - cohere_routes.py Bypasses The Safety Pipeline Entirely

cohere_routes.py calls _provider.chat() / chat_stream() directly (lines 125, 171) with no run_full_pipeline. All provider routes must converge on one safety entry point.

### Gap 6 - llm_judge Latency On Slow Ollama (Injection)

The injection pipeline's llm_judge calls Ollama (llama3.2:1b) with 2s timeout. On the slow Docker-Ollama stack it will always time out and fail-open. Gate behind a flag; document it requires a warm/fast LLM.

### Gap 7 - Factory Cloud Branches Are Dead Code (Silent Fallback Risk)

provider_factory.py aws/azure/gcp branches log "not implemented" and fall back to local. For P3/P4 they must fail loudly (raise) so a misconfigured SAFETY_PROVIDER=aws does not silently run regex.

### Gap 8 - Argument-Mapping Shim For Hallucination

Interface is detect_hallucination(claim, source); the service endpoint takes context, response, domain, trace_id. The provider needs a mapping shim (source->context, claim->response, default domain="general").

---

## 11. Migration From Current State

| Current Problem | Blueprint Fix |
|---|---|
| Two safety stacks (real services + dead interface) | One pipeline to capability registry to real providers (hybrid) |
| Regex-only injection | Defense-in-depth cascade (regex -> ML -> LLM judge) |
| Indirect injection unaddressed | Named requirement + Lakera / mDeBERTa path |
| Monolithic SafetyProvider | Per-capability routing |
| Budget CRUD exists but unenforced | Threshold gate wired into request path (P2) |
| Three overlapping cost implementations | One DB-backed system (team_budgets + usage_logs) |
| Bias keyword stub conflicts with EU AI Act | Demote: interface slot, disabled, offline eval |
| Bedrock/LiteLLM commoditize the ML | Moat = secure+controlled bundle + Canadian PII + on-prem |
| Streaming + cohere routes bypass safety | All routes converge on one interface-driven pipeline (Gaps 4/5) |
| No inter-service auth for hybrid topology | Shared service token (Gap 1) |
| redact_pii is gateway regex, not ML | Presidio anonymizer endpoint on guardrails (Gap 2) |

---

## 12. OWASP / NIST Coverage Map

| Framework Item | Blueprint Coverage |
|---|---|
| OWASP LLM01 (prompt injection) | Injection cascade (regex → Prompt-Guard/Lakera → LLM judge) |
| OWASP LLM06 (sensitive info disclosure) | PII redaction (Presidio + Canada) |
| OWASP LLM08 (excessive agency) | Agent/MCP tool access control |
| OWASP LLM09 (overreliance / hallucination) | Hallucination NLI |
| NIST AI RMF — Govern | Policy engine + RBAC |
| NIST AI RMF — Measure | Budget tracking + anomaly detection + audit |
| NIST AI RMF — Manage | Immutable audit trail + incident response |