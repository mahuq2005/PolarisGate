# PolarisGate → Enterprise AI Platform Pivot

## Cloud-Native, Multi-Marketplace, Interface-Based Architecture

**Document Version:** 1.0  
**Date:** July 30, 2026  
**Purpose:** Complete transformation plan — from self-hosted LLM safety gateway to enterprise AI platform deployable on any cloud or on-prem.

---

## Table of Contents

1. [Role Mapping: Lead AI Platform Enablement](#1-role-mapping-lead-ai-platform-enablement)
2. [Current State: What PolarisGate Has Today](#2-current-state-what-polarisgate-has-today)
3. [Gap Analysis: Platform vs. Cloud](#3-gap-analysis-platform-vs-cloud)
4. [Target Architecture: Interface-Based, Two-Product](#4-target-architecture-interface-based-two-product)
5. [Product 1: PolarisGate On-Prem](#5-product-1-polarisgate-on-prem)
6. [Product 2: PolarisGate Cloud](#6-product-2-polarisgate-cloud)
7. [Code Structure After Refactor](#7-code-structure-after-refactor)
8. [Implementation Roadmap](#8-implementation-roadmap)
9. [How Cloud Porting Works Later](#9-how-cloud-porting-works-later)
10. [Competitive Landscape & Market Positioning](#10-competitive-landscape--market-positioning)

---

## 1. Role Mapping: Lead AI Platform Enablement

### What This Role Actually Does

The Lead AI Platform Enablement role is a hybrid of three functions:

| Hat | % of Time | What You Do |
|-----|:---------:|-------------|
| **Platform Engineer** | 40% | Build LLM pipelines, agent workflows, AWS infra, IaC |
| **Security/Compliance Lead** | 30% | Negotiate with InfoSec/Legal, implement controls, maintain audit evidence |
| **User Support & Enablement** | 30% | Onboard teams, manage budgets/quotas, troubleshoot, write docs |

### The 7 Core Responsibilities

| # | Responsibility | What It Means |
|---|---------------|---------------|
| 1 | **AI Gatekeeper** | Control who uses which AI models, provision access, configure quotas |
| 2 | **Stakeholder Negotiator** | Agree on controls with InfoSec/Risk/Compliance/Legal, get signoffs |
| 3 | **Controls Implementer** | Translate agreed rules into IAM policies, content filters, guardrails, logging |
| 4 | **Budget Owner** | Manage token budgets, credits, quotas, spend alerts across all teams |
| 5 | **User Support (Tier-1)** | Troubleshoot MCP/agent/skills issues, advise on approved patterns |
| 6 | **Platform Builder** | Design/build LLM pipelines, agentic workflows, MCP integrations, RAG (Python + AWS) |
| 7 | **Compliance Evidence Producer** | Document controls, obtain signoffs, maintain audit trail for auditors |

---

## 2. Current State: What PolarisGate Has Today

### Already Built (✅ Done)

| # | Feature | Status | Details |
|---|---------|:------:|---------|
| 1 | Multi-provider LLM Gateway | ✅ | 10 providers (OpenAI, Anthropic, Gemini, Cohere, Mistral, Ollama, DeepSeek, xAI, Groq, Together). Proxy auto-detection, streaming, admin-managed API keys |
| 2 | Content Safety Guardrails | ✅ | Toxicity (keyword → BERT → LLM cascade), PII redaction (not just detection), prompt injection (45 patterns), hallucination (dual NLI ensemble) |
| 3 | RBAC + Access Control | ✅ | JWT + bcrypt (12 rounds), Admin/Safety Officer/Viewer roles, API key management |
| 4 | Rate Limiting | ✅ | Per-endpoint rate limiting (200/min default) |
| 5 | Audit Trail + Compliance Docs | ✅ | Immutable audit trail, 8 compliance docs (SOC 2, GDPR, HIPAA, ISO 27001, PCI DSS, NIST AI RMF, EU AI Act, AIDA) |
| 6 | Policy Engine | ✅ | 13 configurable YAML policies with toggle switches, action/severity selectors |
| 7 | Dashboard + UI | ✅ | 7 summary cards, incident management, chat UI, batch testing, content analysis |
| 8 | Monitoring | ✅ | Prometheus + Grafana, OpenTelemetry tracing, circuit breaker pattern, webhooks |
| 9 | Testing Framework | ✅ | ~100 tests across 4 layers (strategy, contract, integration, E2E), 52 test vectors |
| 10 | K8s + Docker | ✅ | Helm chart (`k8s/helm/polarisgate/`), Docker Compose (14 services), Dockerfile.fips |
| 11 | Python SDK | ✅ | `pip install polarisgate` — check, redact, stream, batch |
| 12 | Multi-language UI | ✅ | English, Français, العربية |
| 13 | Self-Hosted | ✅ | 100% self-hosted, Docker Compose in 2 minutes, air-gap build scripts |

### Competitive Position

PolarisGate is the ONLY platform with ALL of:
- Self-Hosted + Open Source
- Dashboard + Audit Trail
- PII Redaction (not just detection)
- Hallucination Detection
- Prompt Injection Detection
- Batch Testing + Webhooks
- Multi-Provider LLM Gateway

---

## 3. Gap Analysis: Platform vs. Cloud

### Shared Platform Gaps (Build Once, Both Products Get)

These features are missing regardless of deployment target:

| # | Gap | Category | Effort | Priority |
|---|-----|----------|--------|----------|
| **S1** | Interface-based architecture refactor | Foundation | 2 weeks | P0 |
| **S2** | Token counting middleware | Cost | 1 week | P0 |
| **S3** | Budget management & quota enforcement | Cost | 1.5 weeks | P0 |
| **S4** | Cost dashboards & anomaly detection | Cost | 1 week | P0 |
| **S5** | Enterprise SSO (Okta, Azure AD, LDAP) | Auth | 1 week | P0 |
| **S6** | Multi-tenant onboarding workflow | Platform | 1 week | P1 |
| **S7** | Continuous accuracy monitoring | Quality | 1 week | P1 |
| **S8** | Agent/MCP server hosting | Platform | 2 weeks | P1 |
| **S9** | RAG pipeline (PGVector) | Platform | 2 weeks | P1 |
| **S10** | Graph RAG (Neo4j) | Platform | 1 week | P1 |
| **S11** | Provider fallback chains | Reliability | 0.5 weeks | P1 |
| **S12** | Responsible AI framework | Governance | 1 week | P2 |
| **S13** | Feature flags system | Infra | 0.5 weeks | P2 |
| **S14** | Data classification labels | Governance | 0.5 weeks | P2 |
| **S15** | Data retention & GDPR erasure | Governance | 0.5 weeks | P2 |
| **S16** | Incident response automation | Operations | 1 week | P2 |
| **S17** | SLI/SLO framework | Operations | 0.5 weeks | P2 |
| **S18** | DevSecOps CI pipeline | Infra | 1 week | P2 |
| **S19** | Alembic migration framework | Infra | 0.5 weeks | P2 |
| **S20** | Runbooks & self-service docs | Enablement | 1 week | P2 |
| **S21** | WCAG 2.1 AA accessibility | UI | 1 week | P3 |
| **S22** | Ragas evaluation integration | Quality | 0.5 weeks | P1 |

**Total Shared Effort: ~22 weeks** (parallelizable)

### On-Prem Only Gaps

| # | Gap | Effort |
|---|-----|--------|
| **O1** | LocalSafetyProvider (wrap BERT + regex + NLI) | 1 week |
| **O2** | FIPS 140-2 crypto hardening | 0.5 weeks |
| **O3** | Air-gap build & deployment guide | 0.5 weeks |
| **O4** | LDAP/AD integration | 0.5 weeks |
| **O5** | Offline license validation | 0.5 weeks |
| **O6** | LocalInfraProvider (Docker Compose + K8s) | 0.5 weeks |
| **O7** | PGVector setup (PostgreSQL extension) | 0.5 weeks |
| **O8** | Neo4j Community container | 0.5 weeks |

**Total On-Prem: ~4.5 weeks**

### Cloud Only Gaps (Per Cloud)

| # | Gap | AWS | Azure | GCP |
|---|-----|:---:|:---:|:---:|
| **C1** | CloudSafetyProvider (Comprehend, AI Safety, DLP) | 1.5w | 1.5w | 1.5w |
| **C2** | Cloud LLM Provider (Bedrock, Azure OpenAI, Vertex AI) | 1w | 1w | 1w |
| **C3** | Terraform module | 1w | 1w | 1w |
| **C4** | Cloud-native IaC (CFN, ARM, DM) | 1w | 1w | 1w |
| **C5** | Container registry (ECR, ACR, GAR) | 0.5w | 0.5w | 0.5w |
| **C6** | Managed services wiring (RDS, ElastiCache, etc.) | 1w | 1w | 1w |
| **C7** | PrivateLink / VPC Endpoints | 0.5w | 0.5w | 0.5w |
| **C8** | Multi-region DR | 1w | 1w | 1w |
| **C9** | Cross-account deployment | 0.5w | 0.5w | 0.5w |
| **C10** | Serverless option (Lambda/Container Apps/Cloud Run) | 1w | 1w | 1w |
| **C11** | Cost analytics (Glue+Athena, Data Factory, Dataflow) | 1w | 1w | 1w |
| **C12** | BI Dashboard (QuickSight, Power BI, Looker) | 0.5w | 0.5w | 0.5w |
| **C13** | Marketplace listing + metering | 1w | 1w | 1w |
| **C14** | FedRAMP / GovCloud (AWS only) | 2w | N/A | N/A |
| **C15** | Managed vector DB (OpenSearch, AI Search, Vertex AI) | 0.5w | 0.5w | 0.5w |
| **C16** | Managed graph DB (Neptune, Cosmos Gremlin, Neo4j Aura) | 0.5w | 0.5w | 0.5w |

**Total Per Cloud: ~14 weeks (AWS), ~13 weeks (Azure), ~13 weeks (GCP)**

---

## 4. Target Architecture: Interface-Based, Two-Product

### The Key Principle

**Build local implementations of every interface. The interfaces ARE the cloud hooks.**

When we later add AWS, we only need to:
1. Write `AWSSafetyProvider` (implements existing `SafetyProvider` interface)
2. Write a CloudFormation template
3. Change `SAFETY_PROVIDER=local` to `SAFETY_PROVIDER=aws`

The core platform, all 22 shared gaps, every line of gateway/policy engine/dashboard code — stays identical.

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             POLARISGATE SHARED CORE                                      │
│                           (Identical code in BOTH versions)                              │
│                                                                                          │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│   │ Gateway  │  │ Policy   │  │  RBAC    │  │  Audit   │  │  Cost    │  │ Dashboard  │ │
│   │ (FastAPI)│  │ Engine   │  │  + Keys  │  │  Trail   │  │ Tracker  │  │ + Chat UI  │ │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘ │
│        └──────────────┴─────────────┴─────────────┴─────────────┴───────────────┘        │
│                                          │                                                │
│                              ┌───────────┴───────────┐                                   │
│                              │    PROVIDER INTERFACES │                                   │
│                              │                        │                                   │
│                              │  SafetyProvider        │                                   │
│                              │  LLMProvider           │                                   │
│                              │  AuthProvider          │                                   │
│                              │  InfraProvider         │                                   │
│                              └───────────┬───────────┘                                   │
│                                          │                                                │
│   ┌──────────┐ ┌───────────┐ ┌─────────────────────┐ ┌────────────────────────────────┐ │
│   │  Agent   │ │ RAG Pipe  │ │ Accuracy Monitor    │ │ Other Shared Services          │ │
│   │  Host    │ │ + Graph   │ │ + Ragas + Fairness  │ │ Feature Flags, Data Labels,    │ │
│   │  MCP Mgr │ │ (PGVector)│ │ + Model Cards       │ │ Retention, Incident Response   │ │
│   └──────────┘ └───────────┘ └─────────────────────┘ └────────────────────────────────┘ │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                    │                                                      │
                    ▼                                                      ▼
┌──────────────────────────────────────┐    ┌──────────────────────────────────────────────┐
│     POLARISGATE ON-PREM              │    │     POLARISGATE CLOUD                          │
│     (Self-Hosted, Air-Gapped)        │    │     (Marketplace, Cloud-Native)                │
├──────────────────────────────────────┤    ├──────────────────────────────────────────────┤
│                                      │    │                                                │
│  SAFETY (ALL LOCAL)                  │    │  SAFETY (CLOUD-NATIVE AI SERVICES)             │
│  Toxicity: BERT + Keyword            │    │  Toxicity: AWS Comprehend / Azure AI Safety    │
│  PII: 45 Regex patterns              │    │  PII: Comprehend / Azure AI Language / DLP    │
│  Injection: 45 Regex patterns        │    │  Injection: Bedrock Guardrails / Vertex AI    │
│  Hallucination: Dual NLI local       │    │  Hallucination: Bedrock Claude NLI             │
│  Bias: Local scoring                 │    │  Bias: SageMaker / Azure ML / Vertex AI       │
│                                      │    │                                                │
│  LLM PROVIDERS                       │    │  LLM PROVIDERS                                 │
│  Ollama (Llama, Qwen, Phi)           │    │  AWS Bedrock + Azure OpenAI + Vertex AI       │
│  + External APIs (opt-in)            │    │  + All external APIs (same as on-prem)         │
│                                      │    │                                                │
│  AUTH                                │    │  AUTH                                          │
│  Local JWT + LDAP/Active Directory   │    │  Local JWT + AWS IAM / Entra ID / GCP Identity│
│                                      │    │  + Okta + Azure AD                             │
│                                      │    │                                                │
│  INFRASTRUCTURE                      │    │  INFRASTRUCTURE (Serverless-Container Hybrid)   │
│  Docker Compose / K8s / OpenShift    │    │                                                │
│  Rancher / Air-Gapped                │    │  ┌──────────────────────────────────────────┐  │
│  Local PostgreSQL + Redis            │    │  │ SERVERLESS LAYER (Lambda/Cloud Functions)│  │
│  FIPS 140-2 Crypto                   │    │  │ • Document ingestion (S3→Lambda)        │  │
│  No cloud dependency                 │    │  │ • Accuracy monitor (scheduled cron)      │  │
│                                      │    │  │ • Anomaly detection (EventBridge)        │  │
│  DEPLOYMENT                          │    │  │ • Webhook notifications                  │  │
│  docker compose up                   │    │  │ • Trace collector (Kinesis→Lambda)       │  │
│  helm install (vanilla K8s)          │    │  │ • License validation (API Gateway)       │  │
│  Air-gap: USB/manual transfer        │    │  └──────────────────────────────────────────┘  │
│  Offline license file                │    │                                                │
│                                      │    │  ┌──────────────────────────────────────────┐  │
│  RAG & VECTOR DB                     │    │  │ CONTAINER LAYER (ECS Fargate/Container    │  │
│  PGVector (built-in PostgreSQL)      │    │  │ Apps/Cloud Run — always warm, streaming)  │  │
│  Neo4j Community (local graph)       │    │  │ • Gateway (FastAPI + WebSocket SSE)      │  │
│                                      │    │  │ • Cost Tracker (token counting)           │  │
│                                      │    │  │ • Agent Host (long-running agents)        │  │
│                                      │    │  │ • RAG Retrieval (vector search)           │  │
│                                      │    │  └──────────────────────────────────────────┘  │
│                                      │    │                                                │
│                                      │    │  ┌──────────────────────────────────────────┐  │
│                                      │    │  │ MANAGED AI (zero-ops ML)                  │  │
│                                      │    │  │ • Bedrock / Azure OpenAI / Vertex AI      │  │
│                                      │    │  │ • Comprehend / AI Safety / DLP            │  │
│                                      │    │  │ • SageMaker Serverless / Azure ML /       │  │
│                                      │    │  │   Vertex AI Endpoints                     │  │
│                                      │    │  └──────────────────────────────────────────┘  │
│                                      │    │                                                │
│                                      │    │  ┌──────────────────────────────────────────┐  │
│                                      │    │  │ MANAGED INFRA (zero-ops databases)        │  │
│                                      │    │  │ • Aurora Serverless v2 / Azure DB /       │  │
│                                      │    │  │   Cloud SQL (auto-scaling)                │  │
│                                      │    │  │ • ElastiCache Serverless / Azure Cache /  │  │
│                                      │    │  │   Memorystore                             │  │
│                                      │    │  │ • S3+CloudFront / Storage+CDN / GCS+CDN  │  │
│                                      │    │  │ • PrivateLink + VPC Endpoints             │  │
│                                      │    │  └──────────────────────────────────────────┘  │
│                                      │    │                                                │
│                                      │    │  DEPLOYMENT                                    │
│                                      │    │  1-Click: CloudFormation / ARM / DM            │
│                                      │    │  Terraform: terraform apply                    │
│                                      │    │  Marketplace: Subscribe → Deploy               │
│                                      │    │                                                │
│                                      │    │  RAG & VECTOR DB                               │
│                                      │    │  OpenSearch / Pinecone / Weaviate (managed)    │
│                                      │    │  Neptune / Cosmos DB / Neo4j Aura              │
└──────────────────────────────────────┘    └──────────────────────────────────────────────┘
```

---

## 5. Product 1: PolarisGate On-Prem

**Target:** Defense, intelligence, healthcare, finance — organizations that CANNOT send data to any cloud.

### Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Safety | Local BERT, regex, dual NLI | ALL models run on local hardware, zero internet |
| LLM | Ollama (Llama, Qwen, Phi) + optional external APIs | External APIs are opt-in, disabled by default |
| Auth | Local JWT + LDAP/Active Directory | On-prem AD integration |
| Infra | Docker Compose, vanilla K8s, OpenShift, Rancher | No cloud-specific services |
| Database | Local PostgreSQL 15 | Single instance or replicated |
| Cache | Local Redis | Single instance |
| Monitoring | Local Prometheus + Grafana | Self-contained |
| Vector DB | PGVector (PostgreSQL extension) | Zero additional infrastructure |
| Graph DB | Neo4j Community Edition (local) | Self-hosted knowledge graph |
| LLM Safety Models | BERT, NLI ensemble, keyword lists | Packaged with deployment |
| Security | FIPS 140-2, air-gapped mode, offline license file | No phone-home |
| Deployment | `docker compose up`, `helm install`, USB air-gap transfer | No cloud account needed |
| Cost Tracking | Token counting → local PostgreSQL → Grafana dashboards | Self-contained |

### Deployment

```bash
# 1. Clone
git clone https://github.com/polarisgate/polarisgate.git
cd polarisgate

# 2. Configure
cp .env.example .env
# Set: SAFETY_PROVIDER=local
# Set: AUTH_PROVIDER=ldap (or local_jwt)
# Set: INFRA_PROVIDER=local

# 3. Deploy
docker compose -f deploy/on-prem/docker-compose.yml up -d

# 4. Verify
curl http://localhost:8002/health
# → All local services healthy
# → Safety: BERT + Keyword + NLI (all local)
# → LLM: Ollama running llama3.1 locally
# → Zero internet traffic
```

---

## 6. Product 2: PolarisGate Cloud

**Target:** Enterprises on AWS, Azure, or GCP who want managed AI services, one-click deployment, and marketplace billing.

### Architecture: Serverless-Container Hybrid (Not All-K8s, Not All-Serverless)

PolarisGate Cloud uses a **hybrid architecture** — the optimal pattern for AI platform workloads:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    POLARISGATE CLOUD — AWS                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    SERVERLESS LAYER                              │    │
│  │  (Event-driven, scheduled, bursty — cost: ~$0 at idle)          │    │
│  │                                                                  │    │
│  │  CloudFront + S3         → Frontend (static files)               │    │
│  │  S3 → Lambda             → RAG document ingestion                │    │
│  │  CloudWatch → Lambda     → Daily accuracy evaluation             │    │
│  │  EventBridge → Lambda    → Cost anomaly detection (15-min cron)  │    │
│  │  EventBridge → Lambda    → Webhook notifications (Slack/Teams)   │    │
│  │  Kinesis → Lambda        → Trace/log ingestion & enrichment      │    │
│  │  API Gateway → Lambda    → License validation endpoint           │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    CONTAINER LAYER (ECS Fargate)                 │    │
│  │  (Always warm, latency-sensitive, streaming, stateful)          │    │
│  │                                                                  │    │
│  │  ┌──────────────────────┐  ┌──────────────────────┐             │    │
│  │  │  Gateway Service     │  │  Agent Host Service   │             │    │
│  │  │  (0.5 vCPU, 1GB)    │  │  (2 vCPU, 4GB)       │             │    │
│  │  │                      │  │                       │             │    │
│  │  │  • FastAPI app       │  │  • Agent lifecycle    │             │    │
│  │  │  • Chat completions  │  │  • MCP server mgmt    │             │    │
│  │  │  • Proxy routing     │  │  • LangChain/CrewAI   │             │    │
│  │  │  • Streaming (SSE)   │  │  • EFS for state      │             │    │
│  │  │  • Rate limiting     │  │                       │             │    │
│  │  │  • Auth middleware   │  │  Auto-scale: 2-10     │             │    │
│  │  │                      │  │                       │             │    │
│  │  │  Auto-scale: 2-8     │  │  ALB health check     │             │    │
│  │  │  ALB health check    │  │                       │             │    │
│  │  └──────────────────────┘  └──────────────────────┘             │    │
│  │                                                                  │    │
│  │  ┌──────────────────────┐  ┌──────────────────────┐             │    │
│  │  │  Cost Tracker        │  │  RAG Retrieval        │             │    │
│  │  │  (0.25 vCPU, 512MB) │  │  (1 vCPU, 2GB)       │             │    │
│  │  │                      │  │                       │             │    │
│  │  │  • Token counting     │  │  • Vector search      │             │    │
│  │  │  • Budget enforcement │  │  • Graph retrieval    │             │    │
│  │  │  • Cost dash API      │  │  • Re-ranking         │             │    │
│  │  │                      │  │                       │             │    │
│  │  │  Auto-scale: 1-3     │  │  Auto-scale: 1-5     │             │    │
│  │  └──────────────────────┘  └──────────────────────┘             │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    MANAGED AI SERVICES (zero-ops ML)             │    │
│  │                                                                  │    │
│  │  Amazon Bedrock           → LLM inference + Guardrails           │    │
│  │  Amazon Comprehend        → Toxicity detection + PII detection   │    │
│  │  SageMaker Serverless     → Custom ML models (fallback)          │    │
│  │  Bedrock Knowledge Bases  → Managed RAG (optional alternative)   │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    MANAGED INFRASTRUCTURE (zero-ops)             │    │
│  │                                                                  │    │
│  │  Aurora Serverless v2   → PostgreSQL (audit, policies, usage)    │    │
│  │  ElastiCache Serverless → Redis (sessions, rate limiter cache)   │    │
│  │  S3 + CloudFront        → Document storage, frontend, logs       │    │
│  │  CloudWatch + X-Ray     → Logging, metrics, distributed tracing  │    │
│  │  PrivateLink            → Bedrock/Comprehend (no internet egress) │    │
│  │  KMS                    → All data encrypted at rest             │    │
│  │  Secrets Manager        → LLM API keys, JWT secret, DB creds     │    │
│  │  IAM Roles              → Least-privilege per service            │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Hybrid, Not All-K8s (EKS) or All-Serverless (Lambda)

| Decision | For | Against | Verdict |
|----------|-----|---------|---------|
| **Gateway on Lambda** | Pay-per-request | Cold starts kill streaming, provisioned concurrency costs MORE than Fargate, hard to debug, no persistent DB pools | ❌ Fargate |
| **Gateway on EKS** | Standard, well-known | $73/mo control plane, node patching, requires K8s expertise from customer | ❌ Fargate is simpler |
| **Gateway on ECS Fargate** | Always warm, native WebSocket/SSE, persistent DB pools, no cluster to manage, ~$40/mo | None for this workload | ✅ **Winner** |
| **Doc Ingestion on Fargate** | Always warm | Idle 99% of the time, paying for unused capacity | ❌ |
| **Doc Ingestion on Lambda** | Event-driven, $0 at idle, scales to zero | None for this workload | ✅ **Winner** |
| **Accuracy Monitor on Fargate** | Always warm | Runs 5 min/day, paying for 23h 55min of idle | ❌ |
| **Accuracy Monitor on Lambda** | $0.02/day, cron-triggered | None | ✅ **Winner** |

### Cost Comparison (Mid-Size Enterprise: 10 teams, 10K req/day)

| Architecture | Monthly Compute Cost | Notes |
|-------------|:-------------------:|-------|
| All EKS | ~$800 | $73 control plane + 3 nodes |
| All Lambda | ~$500 | Provisioned concurrency for gateway |
| All Fargate | ~$350 | Paying for idle services |
| **Hybrid (Fargate + Lambda)** | **~$280** | Fargate ($200) + Lambda ($10) + AI services ($70) |

### Technology Stack Per Cloud

| Layer | AWS | Azure | GCP |
|-------|-----|-------|-----|
| Safety (Managed AI) | Comprehend + Bedrock Guardrails | AI Content Safety + AI Language | Cloud DLP + Vertex AI Safety |
| LLM (Managed AI) | Bedrock + external APIs | Azure OpenAI + external APIs | Vertex AI Gemini + external APIs |
| Containers | **ECS Fargate** (not EKS) | **Container Apps** (not AKS) | **Cloud Run** (not GKE) |
| Serverless | Lambda + Step Functions | Azure Functions + Logic Apps | Cloud Functions + Workflows |
| Events | EventBridge | Event Grid | Eventarc |
| Streaming | Kinesis | Event Hubs | Pub/Sub |
| Database | **Aurora Serverless v2** | Azure DB Flexible Server | Cloud SQL |
| Cache | **ElastiCache Serverless** | Azure Cache Redis | Memorystore |
| Frontend | S3 + CloudFront | Storage Account + CDN | GCS + CDN |
| Monitoring | CloudWatch + X-Ray | Application Insights | Cloud Logging + Monitoring |
| Vector DB | OpenSearch Serverless / Pinecone | Azure AI Search | Vertex AI Vector Search |
| Graph DB | Neptune | Cosmos DB Gremlin | Neo4j Aura |
| Cost Analytics | Glue ETL + Athena + QuickSight | Data Factory + Synapse + Power BI | Dataflow + BigQuery + Looker |
| Security | PrivateLink, KMS, FedRAMP | Private Link, Key Vault | VPC SC, Cloud KMS |
| IaC | CloudFormation + Terraform | ARM/Bicep + Terraform | Deployment Manager + Terraform |
| Marketplace | ✅ AWS Marketplace | ✅ Azure Marketplace | ✅ GCP Marketplace |

### Per-Cloud Serverless Container Equivalents

| Concept | AWS | Azure | GCP |
|---------|-----|-------|-----|
| Serverless containers | ECS Fargate | Container Apps | Cloud Run |
| Scale-to-zero supported | ❌ (min=1 required) | ✅ (native) | ✅ (native) |
| Functions | Lambda | Azure Functions | Cloud Functions |
| Workflow orchestration | Step Functions | Logic Apps | Workflows |
| Event routing | EventBridge | Event Grid | Eventarc |

> **Note:** Azure Container Apps and GCP Cloud Run are superior to ECS Fargate for bursty workloads — they support true scale-to-zero. For PolarisGate's always-warm services (Gateway, Agent Host, Cost Tracker, RAG Retrieval), minimum instance count is set to 1. For deployment simplicity, the same Fargate/Container Apps/Cloud Run pattern is used across all clouds.

### Deployment (AWS Example)

```bash
# 1. Find on AWS Marketplace → Subscribe

# 2. Click "Launch CloudFormation Stack"
#    → Provisions: VPC, ECS Fargate cluster, Aurora Serverless v2,
#      ElastiCache Serverless, S3 bucket, IAM roles, Secrets Manager,
#      CloudFront distribution, PrivateLink endpoints
#    → Deploys PolarisGate as ECS services + Lambda functions
#    → Sets: SAFETY_PROVIDER=aws

# 3. Access https://polarisgate.internal.acme.com

# 4. Verify
# → Safety: AWS Comprehend + Bedrock Guardrails
# → LLM: AWS Bedrock + external providers
# → Gateway: ECS Fargate (always warm, auto-scaling 2-8 tasks)
# → Ingestion: Lambda (S3-triggered)
# → Monitoring: Lambda + CloudWatch (scheduled)
# → All data stays in customer's VPC
```

### Deployment Model: Bring Your Own Account (BYOA)

PolarisGate Cloud deploys INTO the customer's cloud account, NOT the vendor's:

```
Customer's AWS Account:
├── VPC (private subnets)
│   ├── ECS Fargate Cluster
│   │   ├── gateway (ECS Service: 2-8 tasks, ALB)
│   │   ├── agent-host (ECS Service: 2-10 tasks, EFS mount)
│   │   ├── cost-tracker (ECS Service: 1-3 tasks)
│   │   └── rag-retrieval (ECS Service: 1-5 tasks)
│   ├── Lambda Functions
│   │   ├── doc-ingestion (S3 trigger)
│   │   ├── accuracy-monitor (CloudWatch scheduled)
│   │   ├── anomaly-detector (EventBridge scheduled)
│   │   ├── webhook-notifier (EventBridge event)
│   │   ├── trace-collector (Kinesis trigger)
│   │   └── license-validator (API Gateway)
│   ├── Aurora Serverless v2 (audit trail, policies, usage, conversations)
│   ├── ElastiCache Serverless (sessions, rate limiting cache)
│   ├── S3 (documents, logs, frontend, exports)
│   ├── CloudFront (frontend CDN)
│   ├── Secrets Manager (customer's LLM API keys)
│   └── CloudWatch + X-Ray (logs, metrics, traces)

VENDOR (PolarisGate):
├── ECR: container images (gateway, agent-host, cost-tracker, rag-retrieval)
├── S3: Lambda deployment packages, CloudFormation templates, Terraform modules
└── License server: validates subscription (API Gateway + Lambda)
```

**Customer's data NEVER leaves their AWS account. Vendor has ZERO access.**

---

## 7. Code Structure After Refactor

```
polarisgate/
├── services/
│   ├── shared/                          # ← SHARED CODE (both products)
│   │   ├── interfaces/                  # Abstract contracts
│   │   │   ├── __init__.py
│   │   │   ├── safety.py                # SafetyProvider ABC + dataclasses
│   │   │   ├── llm.py                   # LLMProvider ABC
│   │   │   ├── auth.py                  # AuthProvider ABC
│   │   │   └── infra.py                 # InfraProvider ABC
│   │   │
│   │   ├── providers/                   # Implementations
│   │   │   ├── __init__.py
│   │   │   ├── local_safety.py          # ← ON-PREM: BERT + regex + NLI
│   │   │   ├── aws_safety.py            # ← CLOUD: Comprehend + Bedrock
│   │   │   ├── azure_safety.py          # ← CLOUD: AI Safety + Language
│   │   │   ├── gcp_safety.py            # ← CLOUD: DLP + Vertex AI
│   │   │   ├── local_auth.py            # ← BOTH: JWT
│   │   │   ├── okta_auth.py             # ← BOTH: SAML 2.0
│   │   │   ├── azure_ad_auth.py         # ← CLOUD + ON-PREM: OIDC
│   │   │   ├── ldap_auth.py             # ← ON-PREM: AD/OpenLDAP
│   │   │   ├── local_infra.py           # ← ON-PREM: Docker/K8s
│   │   │   ├── aws_infra.py             # ← CLOUD: EKS/Fargate
│   │   │   ├── azure_infra.py           # ← CLOUD: AKS
│   │   │   └── gcp_infra.py             # ← CLOUD: GKE
│   │   │
│   │   ├── provider_factory.py          # Creates provider from env var
│   │   ├── token_counter.py             # ← SHARED: token counting middleware
│   │   ├── feature_flags.py             # ← SHARED: config-driven toggles
│   │   ├── data_classification.py       # ← SHARED: sensitivity labels
│   │   ├── responsible_ai.py            # ← SHARED: bias/model cards
│   │   ├── db.py                        # Existing DB pool
│   │   ├── redis_client.py              # Existing Redis client
│   │   ├── audit.py                     # Existing audit logging
│   │   ├── telemetry.py                 # Existing OpenTelemetry
│   │   └── logging.py                   # Existing logging setup
│   │
│   ├── gateway/                         # ← SHARED: FastAPI gateway
│   │   └── app/
│   │       ├── main.py                  # Modified: new routers, feature flags
│   │       ├── routers/
│   │       │   ├── chat.py              # Modified: uses safety provider interface
│   │       │   ├── proxy.py             # Modified: uses safety provider interface
│   │       │   ├── admin_providers.py   # Unchanged
│   │       │   └── ...
│   │       ├── providers/               # Extended: count_tokens(), get_pricing()
│   │       │   ├── base.py              # Modified: add abstract methods
│   │       │   ├── openai_compat.py     # Modified: implement token counting
│   │       │   ├── anthropic.py         # Modified: implement token counting
│   │       │   └── ...
│   │       └── safety/
│   │           └── pipeline.py           # Refactored: uses safety provider
│   │
│   ├── frontend/                        # ← SHARED: SPA UI
│   │   └── public/
│   │       ├── index.html               # Modified: accessibility + new tabs
│   │       ├── css/styles.css           # Modified: WCAG 2.1 + new styles
│   │       └── js/app.js                # Modified: Cost + Agent + RAG tabs
│   │
│   ├── cost-tracker/                    # ← SHARED: NEW microservice
│   │   ├── Dockerfile
│   │   └── app/
│   │       ├── main.py                  # FastAPI app
│   │       ├── budgets.py               # Budget CRUD + enforcement
│   │       ├── dashboards.py            # Cost dashboard API
│   │       └── anomaly.py               # Anomaly detection
│   │
│   ├── agent-host/                      # ← SHARED: NEW microservice
│   │   ├── Dockerfile
│   │   └── app/
│   │       ├── main.py                  # Agent lifecycle API
│   │       ├── mcp_server.py            # MCP server registry
│   │       └── connectors.py            # LangChain + CrewAI connectors
│   │
│   ├── rag-pipeline/                    # ← SHARED: NEW microservice
│   │   ├── Dockerfile
│   │   └── app/
│   │       ├── main.py                  # Ingestion → retrieval → generation
│   │       ├── ingestion.py             # Document processing
│   │       ├── embedding.py             # Embedding generation
│   │       ├── retrieval.py             # Semantic search
│   │       └── graph_rag.py             # Knowledge graph + graph retrieval
│   │
│   ├── accuracy-monitor/                # ← SHARED: NEW microservice
│   │   ├── Dockerfile
│   │   └── app/
│   │       ├── main.py                  # Scheduled evals
│   │       ├── drift_detector.py         # Accuracy drift detection
│   │       └── ragas_eval.py            # Ragas integration
│   │
│   ├── license-server/                  # ← SHARED: NEW microservice
│   │   └── app/main.py
│   │
│   └── collector/                       # ← SHARED: trace ingestion
│
├── deploy/
│   ├── on-prem/                         # ← ON-PREM deployment configs
│   │   ├── docker-compose.yml           # All services (local providers)
│   │   ├── docker-compose.airgap.yml    # Air-gapped variant
│   │   └── values.yaml                  # Helm values for vanilla K8s
│   │
│   ├── aws/                             # ← CLOUD: AWS deployment
│   │   ├── terraform/                   # terraform-aws-polarisgate module
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   ├── vpc.tf
│   │   │   ├── eks.tf
│   │   │   ├── rds.tf
│   │   │   ├── iam.tf
│   │   │   └── helm.tf
│   │   ├── cloudformation.yaml          # One-click deploy
│   │   └── marketplace/                 # Listing assets
│   │
│   ├── azure/                           # ← CLOUD: Azure deployment
│   │   ├── terraform/                   # terraform-azurerm-polarisgate
│   │   ├── azuredeploy.json             # ARM template
│   │   └── marketplace/
│   │
│   └── gcp/                             # ← CLOUD: GCP deployment
│       ├── terraform/                   # terraform-google-polarisgate
│       ├── deployment.yaml              # Deployment Manager
│       └── marketplace/
│
├── scripts/
│   ├── migrations/                      # ← NEW: Alembic migrations
│   │   ├── env.py
│   │   ├── versions/
│   │   │   ├── 001_usage_logs.py
│   │   │   ├── 002_team_budgets.py
│   │   │   ├── 003_conversations.py
│   │   │   └── 004_data_labels.py
│   │   └── alembic.ini
│   └── ... (existing scripts)
│
├── docs/
│   ├── on-prem/                         # ← ON-PREM docs
│   │   ├── airgap-setup.md
│   │   ├── fips-configuration.md
│   │   └── offline-license.md
│   │
│   ├── cloud/                           # ← CLOUD docs
│   │   ├── aws-marketplace.md
│   │   ├── azure-marketplace.md
│   │   └── gcp-marketplace.md
│   │
│   ├── runbooks/
│   │   ├── onboarding.md
│   │   ├── troubleshooting.md
│   │   └── faq.md
│   │
│   └── slos.md
│
├── .github/workflows/                   # ← NEW: CI/CD
│   ├── ci.yml                           # Full pipeline
│   └── security-scan.yml                # SAST + SCA + Container scan
│
├── polaris_cloud_pivot.md               # ← THIS FILE
├── docker-compose.yml                   # Modified: new services
├── .env.example                         # Modified: new env vars
├── pyproject.toml                       # Modified: new dependencies
└── README.md
```

---

## 8. Implementation Roadmap

### Phase 1: Shared Core (Weeks 1–8)

```
W1-2: Interface Architecture + Gateway Rewire
  ├── Create SafetyProvider, LLMProvider, AuthProvider, InfraProvider interfaces
  ├── Extract LocalSafetyProvider (wrap existing guardrails/hallucination/bias)
  ├── Create ProviderFactory (env-var-based provider selection)
  ├── Rewire Gateway to use interfaces (chat.py, proxy.py)
  ├── Deprecate standalone services (guardrails, hallucination, bias, aida-bridge)
  ├── Set up Alembic migration framework
  └── Test interface contracts

W3-4: Cost Management
  ├── Token counting middleware (intercept LLM calls, count tokens)
  ├── Usage database schema (usage_logs, team_budgets tables)
  ├── Cost-tracker microservice (budgets, quotas, enforcement)
  ├── Cost dashboard UI (budget gauges, trend charts, per-team breakdown)
  ├── Anomaly detection (z-score, Slack/webhook alerts at 80%/90%/100%)
  └── Cost allocation model (showback/chargeback, budget rollover rules)

W5: Enterprise SSO + Onboarding + Accessibility
  ├── AuthProvider interface implementation
  ├── Okta SAML 2.0 provider
  ├── Azure AD OIDC provider
  ├── LDAP/Active Directory provider
  ├── Multi-tenant onboarding workflow (Team CRUD, RBAC assignment, use-case intake)
  ├── Setup wizard (post-deployment: choose cloud, LLMs, safety, auth, budgets)
  ├── WCAG 2.1 AA accessibility improvements
  └── Data classification labels

W6-7: Agent + MCP + RAG + Graph
  ├── Agent host microservice (agent lifecycle, LangChain/CrewAI connectors)
  ├── MCP server registry + management API
  ├── RAG pipeline (ingestion → chunking → embedding → PGVector → retrieval)
  ├── Graph RAG (Neo4j knowledge graph builder, graph-based retrieval)
  ├── Vector DB plugins (PGVector default, Weaviate/Milvus optional)
  ├── Provider fallback chains (OpenAI → Anthropic → Ollama, health-check based)
  └── Ragas evaluation integration

W8: Quality + Governance + DevSecOps + Docs
  ├── Accuracy monitor (daily eval jobs, drift detection, regression alerts)
  ├── Responsible AI framework (bias cards, model cards, fairness dashboard)
  ├── Feature flags system
  ├── Data retention & GDPR erasure API
  ├── Incident response automation (auto-block, quarantine, notify)
  ├── SLI/SLO/SLA framework (latency, availability, accuracy targets)
  ├── DevSecOps CI pipeline (SAST: semgrep/bandit, SCA: safety, Container scan: Trivy)
  └── Runbooks + self-service docs portal
```

### Phase 2: On-Prem Release (Weeks 9–10)

```
W9: On-Prem Safety + Security
  ├── LocalSafetyProvider (wrap existing guardrails/hallucination/bias into interface)
  ├── FIPS 140-2 crypto hardening
  ├── Air-gap build & deployment guide
  ├── LDAP/Active Directory integration
  └── Offline license validation (license file, no phone-home)

W10: On-Prem Infrastructure
  ├── LocalInfraProvider (Docker Compose + K8s management)
  ├── PGVector setup (PostgreSQL extension, migration)
  ├── Neo4j Community container (docker-compose entry)
  └── Final on-prem docker-compose.yml + Helm chart

✅ ON-PREM v3.0 RELEASED
```

### Phase 3: AWS Cloud Release (Weeks 11–14)

```
W11: AWS Safety + LLM
  ├── AWSSafetyProvider (Comprehend for toxicity/PII, Bedrock Guardrails for injection, Bedrock Claude NLI for hallucination)
  ├── Bedrock LLM provider (invoke_model + streaming + token counting)
  └── Terraform AWS module (VPC, EKS, RDS, IAM, PolarisGate Helm release)

W12: AWS Deployment + Networking
  ├── CloudFormation template (one-click deploy)
  ├── ECR image hosting + Helm chart in S3
  ├── Managed services wiring (RDS Aurora, ElastiCache, CloudWatch, Secrets Manager, KMS)
  ├── PrivateLink / VPC Endpoints (no internet egress for AI services)
  └── Cross-account deployment pattern (networking/security/app accounts)

W13: AWS Advanced Features
  ├── Lambda safety microservice (serverless guardrail endpoint)
  ├── Fargate deployment option (ECS Fargate as EKS alternative)
  ├── Multi-region DR (cross-region RDS read replica, S3 replication)
  ├── Glue ETL pipeline (usage_logs → S3 → Glue → Athena tables)
  ├── QuickSight dashboard integration
  └── Performance + penetration testing

W14: AWS Marketplace
  ├── Marketplace listing + metering integration
  ├── License server (subscription validation)
  ├── Security whitepaper + architecture diagram
  ├── SOC 2 Type II audit engagement
  └── FedRAMP package (SSP template, control summary, CRM)

✅ AWS CLOUD v3.0 ON MARKETPLACE
```

### Phases 4–5: Azure + GCP (Weeks 15–16)

```
W15: Azure Cloud
  ├── AzureSafetyProvider (AI Content Safety + AI Language)
  ├── Azure OpenAI LLM provider
  ├── Terraform Azure module
  ├── ARM/Bicep template
  ├── ACR image hosting
  ├── Managed services (Azure DB, Cache, Monitor, Key Vault)
  └── Azure Marketplace listing

W16: GCP Cloud
  ├── GCPSafetyProvider (Cloud DLP + Vertex AI Safety)
  ├── Vertex AI Gemini LLM provider
  ├── Terraform GCP module
  ├── Deployment Manager config
  ├── GAR image hosting
  ├── Managed services (Cloud SQL, Memorystore, Cloud Logging)
  └── GCP Marketplace listing

✅ ALL 3 CLOUDS ON MARKETPLACE
```

---

## 9. How Cloud Porting Works Later

### The Interface Contract

```python
# services/shared/interfaces/safety.py — THE CONTRACT

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

class SafetyProviderType(Enum):
    TOXICITY = "toxicity"
    PII_DETECTION = "pii_detection"
    PII_REDACTION = "pii_redaction"
    INJECTION = "injection"
    HALLUCINATION = "hallucination"
    BIAS = "bias"

@dataclass
class ToxicityResult:
    toxic: bool
    score: float
    categories: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    latency_ms: float = 0.0

@dataclass
class PIIResult:
    detected: bool
    types: List[str] = field(default_factory=list)
    redacted_text: Optional[str] = None
    confidence: float = 0.0
    latency_ms: float = 0.0

@dataclass
class InjectionResult:
    detected: bool
    score: float
    patterns_matched: List[str] = field(default_factory=list)
    latency_ms: float = 0.0

@dataclass  
class HallucinationResult:
    hallucinated: bool
    confidence: float
    model_used: str = ""
    evidence: Optional[str] = None
    latency_ms: float = 0.0

@dataclass
class BiasResult:
    biased: bool
    dimensions: Dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0


class SafetyProvider(ABC):
    """Every cloud/local implementation extends this."""
    
    @abstractmethod
    async def detect_toxicity(self, text: str, context: dict = None) -> ToxicityResult:
        """Check text for toxic content."""
        ...
    
    @abstractmethod
    async def detect_pii(self, text: str, context: dict = None) -> PIIResult:
        """Detect PII in text."""
        ...
    
    @abstractmethod
    async def redact_pii(self, text: str, context: dict = None) -> PIIResult:
        """Detect AND redact PII in text."""
        ...
    
    @abstractmethod
    async def detect_injection(self, text: str, context: dict = None) -> InjectionResult:
        """Check for prompt injection attempts."""
        ...
    
    @abstractmethod
    async def detect_hallucination(self, claim: str, source: str = None) -> HallucinationResult:
        """Check if text contains hallucinations against source."""
        ...
    
    @abstractmethod
    async def check_bias(self, text: str, context: dict = None) -> BiasResult:
        """Check text for bias."""
        ...
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check if the safety provider is operational."""
        ...
    
    @abstractmethod
    def get_capabilities(self) -> Dict[SafetyProviderType, bool]:
        """Return which capabilities this provider supports."""
        ...
```

### Provider Factory (Zero-Code Cloud Switch)

```python
# services/shared/provider_factory.py
import os
from shared.interfaces.safety import SafetyProvider

def create_safety_provider() -> SafetyProvider:
    """Factory — reads env/config, returns correct provider.
    
    Core platform NEVER knows which cloud it's on.
    It just calls this factory and gets a SafetyProvider.
    """
    provider_type = os.getenv("SAFETY_PROVIDER", "local")
    
    if provider_type == "aws":
        from shared.providers.aws_safety import AWSSafetyProvider
        return AWSSafetyProvider(region=os.getenv("AWS_REGION", "us-east-1"))
    
    elif provider_type == "azure":
        from shared.providers.azure_safety import AzureSafetyProvider
        return AzureSafetyProvider(
            endpoint=os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT"),
            key=os.getenv("AZURE_CONTENT_SAFETY_KEY"),
        )
    
    elif provider_type == "gcp":
        from shared.providers.gcp_safety import GCPSafetyProvider
        return GCPSafetyProvider(project_id=os.getenv("GCP_PROJECT_ID"))
    
    else:  # "local"
        from shared.providers.local_safety import LocalSafetyProvider
        return LocalSafetyProvider()
```

### Gateway Code — Identical Across All Deployments

```python
# services/gateway/app/routers/chat.py
# ← SAME CODE for on-prem AND cloud

from shared.provider_factory import create_safety_provider

safety = create_safety_provider()

async def chat_completions(request):
    # This code NEVER changes between on-prem and cloud
    input_check = await safety.detect_toxicity(text)
    input_pii = await safety.redact_pii(text)
    input_injection = await safety.detect_injection(text)
    
    response = await llm_provider.chat(messages)
    
    output_check = await safety.detect_hallucination(response.text)
    output_pii = await safety.redact_pii(response.text)
    output_toxicity = await safety.detect_toxicity(response.text)
```

### Adding a Cloud Later (3 Steps)

```
Step 1: Write provider implementation
  → services/shared/providers/aws_safety.py
  → Implements existing SafetyProvider interface
  → Uses boto3 to call Comprehend, Bedrock, SageMaker

Step 2: Write infrastructure template
  → deploy/aws/cloudformation.yaml (or terraform/)
  → Provisions VPC, EKS, RDS, IAM, deploys PolarisGate

Step 3: Add to factory
  → Add "aws" case in create_safety_provider()
  
Done. Zero core code changes.
```

---

## 10. Competitive Landscape & Market Positioning

### The Market Gap

```
                          Has Full Platform (Dashboard + Audit + UI)
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
             Self-Hosted        Cloud-Locked       SaaS Only
             (Deploy Anywhere)  (Vendor Lock-in)   (Data Leaves Premises)
                    │               │               │
                    ▼               ▼               ▼
              Preamble ($)     Azure AI Safety    Credo AI ($)
              Robust Intel ($) AWS Guardrails     Arthur AI ($50K+)
              CalypsoAI ($)    Google DLP+Vertex  Aporia
                    │               │               │
                    ▼               ▼               ▼
            ALL are expensive    ALL lock you      ALL send your data
            enterprise-only      to one cloud      to 3rd party
            closed-source
                    
                    ╔══════════════════════════════╗
                    ║     POLARISGATE IS HERE      ║
                    ║  Self-Hosted + Open Source   ║
                    ║  + Full Platform + Gateway   ║
                    ║  + PII Redaction             ║
                    ║  + Hallucination Detection   ║
                    ║  + Audit Trail               ║
                    ║  + FREE (Apache 2.0)         ║
                    ╚══════════════════════════════╝
```

### Competitive Advantages

| Advantage | Why It Matters |
|-----------|---------------|
| **Cloud-agnostic** | Deploy to AWS, Azure, GCP, or on-prem — same code |
| **Self-hosted + data sovereignty** | Data never leaves customer's infrastructure |
| **Open source (Apache 2.0)** | No vendor lock-in, full transparency |
| **Full platform (not a library)** | Dashboard, audit, RBAC, policies — everything in one deploy |
| **PII redaction (not just detection)** | Only 3 of 20 competitors have PII redaction |
| **Hallucination detection** | Only 6 of 20 competitors have it |
| **Multi-provider LLM gateway** | 10+ providers, auto-detection, streaming |
| **Marketplace availability** | Buy through existing cloud commitments (EDP/EA) |
| **Air-gapped capable** | Defense, intelligence, classified environments |
| **Flat pricing** | No per-request pricing like Azure/Google/AWS/Lakera |

### Market Size

| Segment | Size (2026) | Growth |
|---------|:-----------:|:------:|
| AI Safety/Guardrails | $2.1B | 41% CAGR |
| LLM Security (Prompt Injection) | $780M | 52% CAGR |
| AI Governance/Compliance | $3.5B | 35% CAGR |
| **Combined TAM** | **$6.4B** | **~38% CAGR** |

---

## Appendix A: Service Count Evolution

| State | Services | Details |
|-------|:--------:|---------|
| **Current** | 14 | gateway, frontend, guardrails, hallucination-detector, bias-monitor, aida-bridge, collector, postgres, redis, ollama, opa, nginx, prometheus, grafana |
| **After Shared Core** | 18 | gateway, frontend, collector, postgres, redis, ollama, opa, nginx, prometheus, grafana, **cost-tracker**, **agent-host**, **rag-pipeline**, **accuracy-monitor**, **license-server**, **neo4j** |
| **Deprecated** | 4 | guardrails, hallucination-detector, bias-monitor, aida-bridge → collapsed into LocalSafetyProvider |

---

## Appendix B: Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Interface-based architecture** | Core code stays identical across all deployments. One env var swaps implementations. |
| **Two products, one codebase** | On-prem and cloud share 100% of core. Only provider implementations differ. |
| **Bring Your Own Account (BYOA)** | Customer data stays in customer's cloud account. Vendor never sees sensitive data. |
| **Local safety as default** | On-prem works offline, air-gapped, with zero internet. Cloud is opt-in enhancement. |
| **Provider factory pattern** | Centralized provider creation. Adding a cloud = 1 new class + 1 case in factory. |
| **Serverless-container hybrid** | Gateway/agents/retrieval on always-warm containers (ECS Fargate/Container Apps/Cloud Run), ingestion/monitoring/webhooks on event-driven serverless (Lambda/Azure Functions/Cloud Functions). Cheapest AND most scalable pattern. |
| **No GPU on containers** | All ML inference (toxicity, PII, hallucination, LLM) uses managed AI services (Bedrock, Comprehend, SageMaker), not in-container models. Eliminates need for EKS GPU nodes. |
| **Aurora/ElastiCache Serverless** | Zero-ops databases with auto-scaling. No provisioning, no patching, pay-per-use. |
| **CloudFormation/Terraform/ARM/DM** | Infrastructure as Code for every cloud. One-click deploy from marketplace. |
| **Marketplace billing** | Enterprises buy through existing cloud commitments (AWS EDP, Azure EA). |
| **FIPS + air-gap support** | Preserved from current PolarisGate. Critical for defense/government. |
| **PGVector + Neo4j** | Zero additional infrastructure for on-prem. Cloud variants use managed services. |

---

## Appendix C: Configuration File

```yaml
# polarisgate.enterprise.yaml — one file, all config
platform:
  name: "Acme Corp AI Platform"
  branding:
    logo_url: "https://acme.com/logo.png"
    colors:
      primary: "#003366"
      accent: "#FF6600"

deployment:
  type: aws                    # aws | azure | gcp | onprem
  safety_provider: aws         # aws | azure | gcp | local
  auth_provider: azure_ad      # local_jwt | okta | azure_ad | ldap

providers:
  - name: openai
    model_ids: ["gpt-4o", "gpt-4o-mini"]
    rate_limit: 100_per_minute
  - name: bedrock
    model_ids: ["anthropic.claude-v2", "amazon.titan-text"]
  - name: ollama
    model_ids: ["llama3.1:8b"]

safety:
  toxicity:
    provider: aws_comprehend    # aws_comprehend | azure_content_safety | local_bert
    threshold: 0.7
  pii:
    provider: aws_comprehend    # aws_comprehend | azure_language | local_regex
    redaction: true
  injection:
    provider: aws_bedrock       # aws_bedrock | azure_content_safety | local_regex
  hallucination:
    provider: aws_bedrock_nli   # aws_bedrock_nli | azure_openai_nli | local_nli

auth:
  provider: azure_ad
  config:
    tenant_id: "xxx"
    client_id: "xxx"

cost_management:
  budgets:
    - team: "data-science"
      monthly_usd: 5000
      providers: ["openai", "bedrock"]
    - team: "engineering"
      monthly_usd: 2000
      providers: ["bedrock", "ollama"]
  alerts:
    spend_threshold_pct: 80
    anomaly_detection: true
    webhook_url: "https://hooks.slack.com/..."

compliance:
  frameworks: [soc2, gdpr, iso27001]
  audit_retention_days: 2555
  evidence_export: s3_bucket
```

---

**End of Document**