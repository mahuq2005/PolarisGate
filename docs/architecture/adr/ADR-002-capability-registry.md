# ADR-002: Capability registry over a monolithic SafetyProvider

- **Date:** 2026-08-26
- **Status:** Accepted

## Context

The original `SafetyProvider` ABC forced six methods on every implementation
(toxicity, PII detection, PII redaction, injection, hallucination, bias). A
point-solution provider (e.g. Azure Prompt Shields = injection only) would have
to stub the other five — a Liskov substitution violation where the subtype
silently "degrades" by pretending to support capabilities it doesn't.

## Decision

Split `SafetyProvider` into six single-method interfaces and introduce a
`CapabilityRegistry` that routes each capability to its provider independently.

## Consequences

- **Positive:** a point-solution provider is one class + one config line; the
  gateway code never changes; providers can be mixed per feature (Azure injection
  + own PII + own hallucination).
- **Negative:** more moving parts (registry, per-capability config) than a single
  class.
- **Moat:** the registry is the defensible integration — swapping any detector is
  a config change, not a rebuild.
