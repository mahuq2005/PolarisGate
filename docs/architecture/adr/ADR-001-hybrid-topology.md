# ADR-001: Hybrid topology — gateway stays light, ML lives in dedicated services

- **Date:** 2026-08-26
- **Status:** Accepted

## Context

The gateway handles latency-sensitive, stateless work (routing, auth, streaming,
budget gate). The ML (BERT toxicity, Presidio PII, DeBERTa NLI) is heavy and
stateful — models live in memory and load slowly. If we collapsed everything into
one process, the gateway could not scale independently, and every scale-out would
re-load every model.

## Decision

Keep the gateway lightweight. Run the ML in dedicated services
(`guardrails` :8005, `hallucination-detector` :8008) behind the `SafetyProvider`
interface over HTTP.

## Consequences

- **Positive:** gateway scales horizontally without model reloads; ML services own
  their lifecycle; cloud mode runs the *same* ML in-VPC.
- **Negative:** adds inter-service HTTP latency (~50–150 ms in-VPC); requires
  inter-service auth (`X-Service-Token`).
- **Risk:** ML cold-start on scale-out — mitigated by `minReplicas=1` and GPU serving.
