# PolarisGate — User Stories

## Gate Accuracy
- As a platform admin, I want toxicity detection to block hate speech and threats without flagging legitimate criticism, so users aren't unfairly silenced.
- As a compliance officer, I want PII detection to catch SSN, SIN, credit cards, emails, and phone numbers in model outputs, so we don't leak sensitive data.
- As a security engineer, I want prompt injection detection to block jailbreak attempts (DAN, "ignore previous instructions", system override) before they reach our models.
- As a product manager, I want hallucination detection to flag factual errors in AI-generated responses, so our customers can trust the output.

## Monitoring & Operations
- As a DevOps engineer, I want weekly accuracy drift checks with automatic GitHub Issues when recall drops >2%, so I catch model degradation early.
- As a team lead, I want a dashboard showing toxicity/PII/injection trends over 24 hours, so I can spot incidents quickly.
- As a developer, I want accuracy benchmarks to run on every PR with pass/fail thresholds, so I know if my changes break detection quality.

## Testing & Quality
- As a QA engineer, I want 78 automated tests covering accuracy, performance, and reliability to run in CI, so regressions are caught before merge.
- As a contributor, I want a PR template with accuracy checklists so I know what to verify before submitting code.

## Feature Requests
- As a frontend user, I want the dashboard to show demo data immediately after setup, so I can evaluate the product before connecting real models.
- As a mobile user, I want the guardrails check API to respond in < 500ms (p95), so our chatbot doesn't feel sluggish.
- As a Canadian company, I want SIN and health card detection alongside US SSN, so we comply with both jurisdictions.