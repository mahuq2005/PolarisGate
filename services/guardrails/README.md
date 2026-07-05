# Guardrails Service

AI safety guardrails service providing toxicity detection, PII identification, and bias monitoring for LLM outputs.

## Purpose

Provides multi-tier content safety checks:
- **Tier 1** — Keyword-based toxicity filtering (fast, <1ms)
- **Tier 2** — BERT/RoBERTa classifier models (accurate, 50-500ms)
- **Tier 3** — LLM-based evaluation (most accurate, 1-5s)
- **PII Detection** — SIN, credit cards, health cards, passport numbers (Luhn + regex)
- **Bias Analysis** — Fairness scoring across protected attributes

## Port

- **Internal**: `8005`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/guardrails/check` | POST | Run toxicity/PII/bias checks |
| `/api/v1/guardrails/models` | GET | List loaded models |
| `/api/v1/guardrails/stats` | GET | Detection statistics |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_DIR` | `/app/models` | Model storage directory |
| `TOXICITY_THRESHOLD` | `0.7` | Toxicity classification threshold |
| `PII_MASK_MODE` | `mask` | PII handling: `mask`, `block`, `alert` |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama LLM service URL |

## Dependencies

- **Ollama** — LLM-based evaluation (optional tier)
- **PostgreSQL** — Audit logging (via gateway)
- **Gateway Service** — Request routing

## Detection Types

| Check | Method | Accuracy |
|-------|--------|----------|
| `toxicity` | Keyword + BERT + RoBERTa | 95%+ |
| `pii` | Regex + Luhn + ML | 99%+ |
| `sentiment` | BERT-based | 90%+ |
| `bias` | Fairness scoring | 85%+ |