# Hallucination Detector

Multi-model cascade hallucination detection service for verifying factual accuracy of LLM responses.

## Purpose

Detects hallucinations in LLM outputs using a configurable cascade:
1. **Prefilter** — Fast keyword/pattern matching (<1ms)
2. **NLI Detector** — Cross-encoder natural language inference (200ms-1s)
3. **LLM Judge** — Ollama-based fairytale/consistency evaluation (1-5s)
4. **Ensemble** — Weighted combination of all detectors

## Port

- **Internal**: `8008`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/hallucination/detect` | POST | Run hallucination detection |
| `/api/v1/hallucination/stats` | GET | Detection statistics |
| `/api/v1/hallucination/cascade` | GET | Cascade configuration |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama LLM service URL |
| `NLI_MODEL` | `cross-encoder/stsb-roberta-large` | NLI model name |
| `CASCADE_DEPTH` | `3` | Number of cascade levels |
| `HALLUCINATION_THRESHOLD` | `0.5` | Detection threshold |
| `OLLAMA_MODEL` | `tinyllama` | LLM judge model |

## Cascade Architecture

```
Input (context + response)
    │
    ├── Tier 1: Prefilter (keyword overlap, contradiction)
    │         │
    │         ├── Pass → Tier 2
    │         └── Fail → HALLUCINATION (low confidence)
    │
    ├── Tier 2: NLI Detector (cross-encoder)
    │         │
    │         ├── Pass → Tier 3
    │         └── Fail → HALLUCINATION (medium confidence)
    │
    └── Tier 3: LLM Judge (Ollama)
              │
              ├── Pass → FACTUAL (high confidence)
              └── Fail → HALLUCINATION (high confidence)
```

## Dependencies

- **Ollama** — LLM judge model
- **Gateway Service** — Request routing