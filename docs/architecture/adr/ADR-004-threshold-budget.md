# ADR-004: Threshold budget — hard cutoff, no cost prediction

- **Date:** 2026-08-26
- **Status:** Accepted

## Context

Enterprises accept a simple "block when budget is exceeded" as v1. Cost prediction
is error-prone and over-engineered for the first release.

## Decision

Enforce a hard threshold gate: `check_quota(team_id)` before each call (return 402
if exceeded) and `record_usage()` after. No cost prediction.

## Consequences

- **Positive:** deterministic and simple to reason about; no surprise spend.
- **Negative:** no forecasting — teams only learn they're over budget at the moment
  it happens.
- **Moat:** budget *enforcement* (not just tracking) is rare among competitors.
