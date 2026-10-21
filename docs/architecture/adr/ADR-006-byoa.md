# ADR-006: BYOA — deploy into the customer's account, not vendor SaaS

- **Date:** 2026-08-26
- **Status:** Accepted

## Context

Data sovereignty is the differentiator. A vendor-hosted SaaS means customer data
transits and lives in the vendor's infrastructure — which most enterprises (banks,
healthcare, defense, public sector) reject.

## Decision

Deploy PolarisGate **into** the customer's cloud account (AWS/Azure/GCP). The
vendor hosts only container images + IaC templates; the customer owns all data.
Vendor has zero data access.

## Consequences

- **Positive:** data never leaves the customer's control; strong compliance story
  (SOC 2/FedRAMP is *customer* attestation, not vendor).
- **Negative:** per-customer infrastructure (cost + operational surface); the
  upgrade path is "release a new version → customer clicks upgrade in the
  Managed Application / CloudFormation".
- **Moat:** this is deliberately *irreversible* — SaaS would erase the differentiator.
