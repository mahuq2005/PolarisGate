# ADR-005: PII is always our own ML — even in cloud

- **Date:** 2026-08-26
- **Status:** Accepted

## Context

Cloud PII APIs (AWS Comprehend, Azure AI Language PII) are US/English-centric and
do not cover Canadian entities (SIN, health card numbers, Canadian postal codes).
Delegating PII to them would destroy the Canadian-PII moat — the one thing
competitors can't copy.

## Decision

PII detection and redaction always run on our own Presidio + Canadian recognizers,
in-VPC, in **every** deployment (on-prem and cloud). Cloud adds value only on
**injection** (Prompt Shields / Bedrock Guardrails), optionally toxicity/hallucination.

## Consequences

- **Positive:** Canadian PII sovereignty is preserved; PII never leaves the VPC.
- **Negative:** we maintain our own PII recognizers (labeled-data pipeline for
  future custom entities).
- **Moat:** this is a deliberately *irreversible* decision — it's the moat.
