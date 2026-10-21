# ADR-003: Buy injection ML, build PII

- **Date:** 2026-08-26
- **Status:** Accepted

## Context

Prompt-injection detection is commoditized — Prompt-Guard, Lakera, Bedrock
Guardrails, and Azure Prompt Shields all sell it. Canadian PII recognizers
(SIN, health cards, postal codes) are uncopyable — US-centric tools simply don't
have them.

## Decision

Use managed/bought injection detection where it's best-in-class; build our own
PII (Presidio + Canadian recognizers) always in-VPC.

## Consequences

- **Positive:** engineering effort goes to the moat (PII), not the commodity
  (injection); injection defense can be upgraded to a better vendor without
  changing the architecture.
- **Negative:** injection remains a named v1 weakness (Prompt-Guard TPR ~71%).
- **Constraint:** Prompt-Guard's Llama 3.1 license must stay an *optional*,
  license-isolated dependency inside an Apache-2.0 product.
