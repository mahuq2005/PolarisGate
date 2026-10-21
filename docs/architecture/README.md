# Architecture Documentation

This directory is the **single source of truth** for how PolarisGate is built.
If a document answers a question, link it here — don't duplicate it.

## Documents

| Document | What it's for | Audience |
|---|---|---|
| **[TAD.md](TAD.md)** | The Technical Architecture Document — the full 12-section description (arc42 + C4). Start here. | Everyone |
| **[overview.md](overview.md)** | A shorter, narrative overview | Executives, newcomers |
| **[to-be-blueprint.md](to-be-blueprint.md)** | The *design rationale* — the validated target architecture + the 20 gaps that motivated it | Architects |
| **[adr/](adr/)** | Individual Architecture Decision Records (why each decision was made) | Architects, future maintainers |

## Reading order

1. **New to the project?** → `overview.md` → `TAD.md` §1–3.
2. **Implementing a feature?** → `TAD.md` §5 (Building Blocks) + §6 (Runtime) + §8 (Cross-cutting).
3. **Questioning a decision?** → `adr/` (the rationale) → `to-be-blueprint.md` (the original motivation).
4. **Deploying?** → `TAD.md` §7 (Deployment View).

## Conventions

- Architecture documents follow **arc42** (12 sections) and use **C4** diagrams (Mermaid).
- Every architecture change must **update `TAD.md` and add an ADR** in `adr/`.
- Diagrams are written in **Mermaid** (text) so they stay versioned in git — no image files.

## Related (outside this directory)

- `docs/security/` — threat model, incident response, compliance maps
- `docs/compliance/` — SOC 2, GDPR, HIPAA, EU AI Act, NIST AI RMF
- `docs/deployment/` — production deployment guides
- `docs/api/` — API reference
