# ADR-007: Bias demoted — interface slot kept, disabled

- **Date:** 2026-08-26
- **Status:** Accepted

## Context

The existing bias check is a keyword stub — too crude to ship honestly. But the
EU AI Act and NIST AI RMF still *name* bias as a requirement, so we can't just
delete the concept.

## Decision

Keep the `BiasDetector` interface slot, but disable it: it returns "not biased"
and bias is evaluated offline instead of in the request path.

## Consequences

- **Positive:** no false confidence in a crude detector; the interface slot is
  ready for a real bias model later without a re-architecture.
- **Negative:** bias is not detected in real time (known gap for EU AI Act
  compliance).
- **Honesty:** "off" is better than "lying" (a Liskov violation where the subtype
  pretends to detect bias).
