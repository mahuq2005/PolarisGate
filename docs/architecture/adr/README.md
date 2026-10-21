# Architecture Decision Records (ADRs)

Each decision is recorded once, dated, and immutable. When a decision changes,
do **not** edit an old ADR — add a new one and mark the old one *Superseded by*.

## Index

| ADR | Decision | Status |
|---|---|---|
| [ADR-001](ADR-001-hybrid-topology.md) | Hybrid topology — gateway light, ML in dedicated services | Accepted |
| [ADR-002](ADR-002-capability-registry.md) | Capability registry over a monolithic SafetyProvider | Accepted |
| [ADR-003](ADR-003-buy-injection-build-pii.md) | Buy injection ML, build PII | Accepted |
| [ADR-004](ADR-004-threshold-budget.md) | Threshold budget — hard cutoff, no cost prediction | Accepted |
| [ADR-005](ADR-005-pii-own-ml.md) | PII is always our own ML, even in cloud | Accepted |
| [ADR-006](ADR-006-byoa.md) | BYOA — deploy into the customer's account | Accepted |
| [ADR-007](ADR-007-bias-demoted.md) | Bias demoted — interface slot kept, disabled | Accepted |

## Format

Each ADR follows the Nygard format:

1. **Context** — the forces at play (why a decision is needed)
2. **Decision** — what we decided, stated in the imperative
3. **Consequences** — what it makes easier / harder / riskier

## Status values

- **Proposed** — under discussion
- **Accepted** — the current decision
- **Deprecated** — no longer applies (see replacement)
- **Superseded by ADR-xxx** — replaced by a newer decision
