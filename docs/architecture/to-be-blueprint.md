# PolarisGate — To-Be Architecture Blueprint

**Document Version:** 2.0
**Status:** Validated (security / ML / product review + AWS/Azure research)
**Scope:** Target architecture for the enterprise AI adoption platform (on-prem + BYOA cloud)

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
| Azure AI Content Safety | Safety, but Azure-only, no on-prem, no governance/budget |
| Onyx | Agent governance, but SaaS-only, no PII redaction / hallucination |
| Credo AI | Governance, but post-hoc (no runtime blocking), SaaS |
| **PolarisGate** | **Safety + governance + budget + audit + self-hosted, one deployable** |

### The Uncopyable Spears

- **Canadian PII recognizers** (SIN, health card, SWIFT/CUSIP/ISIN) — Comprehend/Azure are US/English-centric; nobody else has these.
- **On-prem / air-gap** — Lakera/Onyx/Credo are SaaS; they cannot ship on-prem.
- **Self-hosted hallucination NLI** — rare; Bedrock/Azure equivalents are cloud-only.

> **Rule:** the moat is NOT the ML. It is orchestration + Canadian PII + the provider-agnostic interface + BYOA + the governance/budget control plane.

---

## 2. Architecture Principles

1. **Capability-level registry** — each safety check (injection / PII / toxicity / hallucination) is an independently routable provider, so best-of-breed tools mix per-feature.
2. **Buy commodity, build differentiators** — buy injection ML (Prompt-Guard / Lakera / Bedrock / Prompt Shields), build Canadian PII + orchestration.
3. **One codebase, N deploy targets** — interface + factory + env var (on-prem + customer's cloud).
4. **Local-first, cloud-escalate** — your own ML is the default everywhere; cloud is additive, only where genuinely better.
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
   │  ML SERVICES (your models — run in customer's VPC, on-prem OR cloud)│
   │  guardrails (BERT + Presidio + Canada recognizers)  :8005           │
   │  hallucination-detector (DeBERTa NLI)               :8008           │
   └─────────────────────────────────────────────────────────────────────┘
         │                                                    │
    ┌────▼─────────┐                                ┌─────────▼────────┐
    │  ON-PREM     │                                │  CLOUD (BYOA)    │
    │  Docker/Helm │                                │  AWS · Azure     │
    └──────────────┘                                └──────────────────┘
```

> **Topology decision (hybrid, not collapse):** the gateway container deliberately has no `torch`/`transformers`/`presidio` — collapsing ML into the gateway would balloon it to ~2–3 GB and slow startup. `LocalSafetyProvider` calls the ML services over HTTP behind the interface. Cloud mode runs the SAME local ML in the customer's VPC, and adds managed cloud services only where they're genuinely better (injection, optional hallucination).

---

## 4. Pillar 1 — Safety (Capability Registry + Injection Cascade)

### Config

```yaml
safety:
  injection:
    cascade: [regex, prompt_guard]   # layer 1 → layer 2; layer 3 = lakera/cloud (premium)
    threshold: 0.5
  pii:
    provider: presidio               # your ML — generic + Canadian (the moat), on-prem AND cloud
    redaction: true
  toxicity:
    provider: bert                   # your BERT (default); cloud option optional
  hallucination:
    provider: deberta_nli            # your DeBERTa NLI (default); cloud option optional
  bias:
    enabled: false                   # demoted: slot retained, offline eval for EU AI Act / NIST
```

### Injection = Defense-in-Depth Cascade

```
Layer 1: regex patterns        → cheap, zero FP, catches known signatures (kept, not removed)
Layer 2: Prompt-Guard-86M      → local ML — or Bedrock Guardrails (AWS) / Prompt Shields (Azure)
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

### Provider Map (AWS + Azure)

| Capability | On-Prem | AWS (BYOA) | Azure (BYOA) |
|---|---|---|---|
| injection | regex + Prompt-Guard | **Bedrock Guardrails** | **Prompt Shields** |
| pii (generic + Canadian) | **Presidio + Canada (moat)** | **Presidio + Canada (moat)** | **Presidio + Canada (moat)** |
| toxicity | BERT | Comprehend (optional) | Analyze Text (optional) |
| hallucination | DeBERTa NLI | Bedrock grounding (optional) | **Groundedness detection** (optional) |
| bias | (off) | (off) | (off) |

> **Key rule:** PII is always your own ML (Presidio + Canada), on-prem AND in cloud. The cloud does NOT replace PII — Comprehend/Azure-Language-PII are US/English-centric and redundant for generic + useless for Canadian. Cloud adds value only on **injection** (your weak spot) and optionally **toxicity/hallucination**.

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
| **P0 — Interface wiring (1 wk)** | `LocalSafetyProvider` → HTTP calls to guardrails/hallucination (hybrid); `pipeline.py` calls `app.state.safety_provider`; injection becomes a cascade; wire hallucination into request path | Interface real, regex kept as layer 1, gateway stays light |
| **P1 — Capability registry (1 wk)** | Monolithic → per-capability ABC + YAML + factory routing | Mix providers per-feature |
| **P2 — Budget loop (3–4 days)** | Wire `check_quota` + `record_usage`; retire legacy `cost_tracker.py` | Budgets have teeth |
| **P3 — Cloud providers (2–3 wk)** | AWS + Azure capability providers (injection via Bedrock/Prompt Shields, optional toxicity/hallucination) + Terraform + PrivateLink | AWS/Azure Marketplace-ready |
| **P4 — GCP (1 wk)** | Same pattern | 3 clouds |
| **P5 — Governance completion** | Agent identity, RAG | Full platform |

> **Dev-machine note (not a product deliverable):** Ollama-in-Docker is slow on Apple Silicon only; Linux+GPU on-prem is fine. Do not treat "fix Ollama" as roadmap work.

---

## 9. Decisions & Rationale

| Decision | Why |
|---|---|
| **Hybrid topology** (LocalSafetyProvider → HTTP, not collapse) | Gateway stays lightweight; ML services keep their models; cloud mode runs the same ML in-VPC |
| **Injection cascade, not swap** | Single-model injection defense is a single point of failure; regex gives zero-FP layer 1 |
| **Capability registry over monolith** | Best-in-class tools are point solutions (Lakera/Bedrock = injection only); per-feature routing lets them mix — and it's mandatory in cloud to keep the Canadian moat |
| **PII = always your own ML** | Comprehend/Azure-Language-PII are US-centric; your Presidio+Canada does generic AND Canadian; cloud PII is redundant/useless |
| **Threshold budget, no cost prediction** | Simple "block when exceeded" is what enterprises accept as v1 |
| **Bias demoted, not dropped** | EU AI Act + NIST AI RMF name bias as a requirement; keyword stub is too crude to ship, so keep the slot + offline eval |
| **Buy injection ML, build PII** | Injection is commoditized (Prompt-Guard/Lakera/Bedrock/Prompt Shields); Canadian PII is the uncopyable moat |
| **Prompt-Guard license-isolated** | Llama 3.1 license inside an Apache-2.0 product must be an optional dependency |

---

## 10. Implementation Gaps (13, Grouped By Layer)

Found by tracing the actual code paths. All must be resolved in or before P0–P4.

### Layer 1 — Request Path Integrity (safety actually runs)

| # | Gap | Severity | Phase |
|---|---|---|---|
| 4 | Streaming routes (`chat.py`/`proxy.py` `/completions/stream`) call `run_input_guardrails` + `chat_stream()` directly — no `check_quota`/`record_usage`, skip the interface | 🔴 | P0 |
| 5 | `cohere_routes.py` calls `_provider.chat()`/`chat_stream()` directly — bypasses `run_full_pipeline` entirely | 🔴 | P0 |
| 9 | `guardrails.py` router has its own `_check_toxicity` + `redact_text` + `detect_injection` — a THIRD inline copy of safety logic | 🔴 | P0 |
| 10 | **Hallucination detection is NOT in the request path at all** — `routers/hallucination.py` is dashboard-only; `run_full_pipeline` never calls the hallucination service | 🔴 | P0 |

### Layer 2 — Interface Wiring (hybrid topology)

| # | Gap | Severity | Phase |
|---|---|---|---|
| 1 | Inter-service auth missing — guardrails `/api/v1/check` requires JWT; no service-token helper exists | 🔴 | P0 |
| 3 | `LocalSafetyProvider.health_check()` hardcodes "ok"; must probe `:8005`/`:8008` | 🟡 | P0 |
| 8 | Hallucination arg-shim — interface `detect_hallucination(claim, source)` vs service `context/response/domain/trace_id` | 🟡 | P0 |
| 11 | `shared/interfaces/llm.py` is dead — live routing uses a separate `gateway/app/providers/*` hierarchy (2 LLM abstractions) | 🟡 | P1 |

### Layer 3 — ML Quality (buy-vs-build)

| # | Gap | Severity | Phase |
|---|---|---|---|
| 2 | PII redaction = gateway regex, no Presidio anonymizer endpoint exposed | 🔴 | P0 |
| 6 | `llm_judge` (injection) calls slow Docker-Ollama with 2s timeout → always fails open | 🟡 | P1 |
| 13 | SDK `redact()` hits `/api/v1/guardrails/check` → regex redaction, not ML | 🟡 | P2 |

### Layer 4 — Cloud (P3/P4)

| # | Gap | Severity | Phase |
|---|---|---|---|
| 7 | Factory `aws`/`azure`/`gcp` branches log "not implemented" and silently fall back to regex | 🔴 | P3 |
| 12 | `agent-host` / `rag-pipeline` / `accuracy-monitor` are stubs (`self.running=True`, ~20 lines) | 🟡 | P5 |

---

## 11. Canadian PII Moat Architecture

### The Design (correction — no separate PII model call)

Your own ML (Presidio + Canadian recognizers) already does **all** PII — generic (email/SSN/phone) AND Canadian (SIN/health card/SWIFT/CUSIP/ISIN). There is **no reason to call Comprehend/Azure-Language-PII** — they're redundant for generic and useless for Canadian.

```
Input text
   ▼
[LAYER 1 — YOUR ML, always, in customer's VPC (on-prem OR cloud)]
   Presidio + Canada recognizers → PII detection + redaction (generic + Canadian)
   ← the moat. ONE call, covers all PII. NOT a separate sidecar, NOT a cloud call.
   ▼
[LAYER 2 — CLOUD, additive only, where genuinely better]
   injection     → Bedrock Guardrails (AWS) / Prompt Shields (Azure)
   toxicity      → optional (Comprehend / Analyze Text) — or skip, BERT is fine
   hallucination → optional (Bedrock grounding / Groundedness) — or skip, DeBERTa is fine
   ▼
LLM call
```

### The `pii_canada` Capability

In the capability registry, Canadian PII is just **one capability** (`pii_canada`) that runs as a thin pre-filter **inside the customer's VPC** — not a separate product, not a sidecar, just a provider behind the interface.

### Future Migration Path (optional, zero core-code change)

Both clouds can train custom entity models, which would let you move `pii_canada` from "local Presidio" to "managed cloud model" behind the same interface:

| Cloud | Managed Canadian-PII Option | Requirements |
|---|---|---|
| AWS | **Custom Comprehend entity recognizer** | labeled training data (annotated docs / entity lists), up to 25 entities |
| Azure | **Custom NER (CNER)** | labeled data, via Foundry Studio |

> **Note:** this requires a labeled-data pipeline you don't have yet. It's a *future* optimization, not a v1 requirement. The v1 approach is "your ML in the VPC," which is simpler and keeps the moat fully under your control.

---

## 12. Cloud-Specific Considerations (AWS + Azure)

| # | Consideration | AWS | Azure |
|---|---|---|---|
| C1 | Canadian PII moat = `pii_canada` thin in-VPC pre-filter | ✅ | ✅ |
| C2 | Future managed-moat path | Custom Comprehend recognizer | Custom NER (CNER) |
| C3 | Injection is the #1 cloud value-add | Bedrock Guardrails | **Prompt Shields** |
| C4 | Identity / secrets / networking | IAM + Secrets Manager + PrivateLink + KMS | Entra ID + Key Vault + Private Link |
| C5 | Data residency for Canadian market | ca-central-1 | **Canada East** |
| C6 | Safety cost metering (managed calls) | Comprehend/Bedrock pricing | Content Safety pricing |

> **Latency note (corrected):** cloud-hosted in-VPC calls to Comprehend/Bedrock are ~50–150ms — not a real concern for BYOA. The only genuine cloud cost is per-request metering, which is small and tracked via the budget pillar.

---

## 13. Migration From Current State

| Current Problem | Blueprint Fix |
|---|---|
| Two safety stacks (real services + dead interface) | One pipeline → capability registry → real providers (hybrid) |
| Regex-only injection | Defense-in-depth cascade (regex → ML → LLM judge) |
| Indirect injection unaddressed | Named requirement + Lakera / mDeBERTa path |
| Monolithic `SafetyProvider` | Per-capability routing |
| Budget CRUD exists but unenforced | Threshold gate wired into request path (P2) |
| Three overlapping cost implementations | One DB-backed system (`team_budgets` + `usage_logs`) |
| Bias keyword stub conflicts with EU AI Act | Demote: interface slot, disabled, offline eval |
| Bedrock/LiteLLM commoditize the ML | Moat = secure+controlled bundle + Canadian PII + on-prem |
| Streaming + cohere routes bypass safety | All routes converge on one interface-driven pipeline (Gaps 4/5/9) |
| **Hallucination not in request path** | Wire it into `run_full_pipeline` output (Gap 10) |
| No inter-service auth for hybrid topology | Shared service token (Gap 1) |
| `redact_pii` is gateway regex, not ML | Presidio anonymizer endpoint on guardrails (Gap 2) |
| Cloud factory silently falls back to regex | Fail loudly on `SAFETY_PROVIDER=aws/azure/gcp` (Gap 7) |

---

## 14. OWASP / NIST Coverage Map

| Framework Item | Blueprint Coverage |
|---|---|
| OWASP LLM01 (prompt injection) | Injection cascade (regex → Prompt-Guard/Bedrock/Prompt Shields → LLM judge) |
| OWASP LLM06 (sensitive info disclosure) | PII redaction (Presidio + Canada) |
| OWASP LLM08 (excessive agency) | Agent/MCP tool access control |
| OWASP LLM09 (overreliance / hallucination) | Hallucination NLI (DeBERTa / Bedrock grounding / Groundedness) |
| NIST AI RMF — Govern | Policy engine + RBAC |
| NIST AI RMF — Measure | Budget tracking + anomaly detection + audit |
| NIST AI RMF — Manage | Immutable audit trail + incident response |

---

## Appendix — AWS vs Azure Service Mapping

| PolarisGate Capability | On-Prem (yours) | AWS Managed | Azure Managed |
|---|---|---|---|
| injection | regex + Prompt-Guard | Bedrock Guardrails (prompt attack filter) | Prompt Shields |
| toxicity | BERT | Comprehend / Bedrock content filter | Analyze Text API |
| PII (generic) | Presidio | (skip — redundant) | (skip — redundant) |
| PII (Canadian) | **Presidio + Canada (moat)** | Custom Comprehend recognizer (future) | Custom NER / CNER (future) |
| hallucination | DeBERTa NLI | Bedrock contextual grounding + Automated Reasoning | Groundedness detection |
| bias | (off) | (off) | (off) |
| data residency | n/a | ca-central-1 | Canada East |





