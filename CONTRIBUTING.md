# Contributing to PolarisGate

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/polarisgate/polarisgate.git
   cd polarisgate
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your secrets
   make setup
   ```

3. **Install pre-commit hooks**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

4. **Build and run**
   ```bash
   make build
   make up
   ```

## Code Style

- **Python**: We use `ruff` for linting and formatting. Run `make lint` before committing.
- **Type hints**: All Python code must have type hints. Run `mypy` to verify.
- **JavaScript/TypeScript**: Follow the existing patterns in `frontend/`.
- **Dockerfiles**: Use `hadolint` for Dockerfile linting (included in pre-commit hooks).

## Testing

- **Unit tests**: `make test` runs the test suite
- **AI/ML tests**: `make test-aiml` runs the AI/ML test suite
- **E2E tests**: `cd tests/e2e && npx playwright test`
- **Coverage**: Ensure your changes maintain or improve coverage
- **Accessibility**: Run `make test-accessibility` for a11y checks
- **Visual regression**: Run `make test-visual` for visual diff tests

## Security Requirements

### Mandatory Checks (Pre-commit)
All code must pass these checks before committing:
- **SAST**: `make sast` — Bandit + Semgrep static analysis
- **Dependency scan**: `make scan-deps` — pip-audit + safety + trivy
- **Secrets detection**: `detect-secrets` (pre-commit hook)
- **SBOM generation**: `make sbom` — CycloneDX format

### Compliance Requirements
- All API endpoints must have audit logging
- All user input must be sanitized
- PII data must be masked in logs
- Rate limiting must be applied to all public endpoints
- Encryption keys must use AES-256-GCM or equivalent
- FIPS mode must be validated for government deployments

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Run the full test suite: `make test && make test-aiml`
4. Run linting: `make lint`
5. Run security checks: `make security-check`
6. Run compliance checks: `make compliance-check`
7. Update CHANGELOG.md with your changes
8. Submit a PR with a clear description of changes
9. PR must be reviewed by at least one maintainer
10. All CI checks must pass before merge

## Architecture

### Service Architecture
```
┌─────────────────────────────────────────────────────┐
│                    Nginx (Reverse Proxy)             │
├─────────────────────────────────────────────────────┤
│  Gateway (Auth, Rate Limit, Audit)                   │
├──────────┬──────────┬──────────┬────────────────────┤
│Guardrails│Hallucin. │ AIDA     │ Bias Monitor       │
│(Tox/PII) │Detector  │ Bridge   │ (Fairness)         │
├──────────┴──────────┴──────────┴────────────────────┤
│  Sidecar Proxy | Kill Switch | Budget Controller    │
├─────────────────────────────────────────────────────┤
│  Semantic Cache | Closed-Loop | Collector           │
├─────────────────────────────────────────────────────┤
│  OPA (Policy Engine) | MLflow | Retraining          │
└─────────────────────────────────────────────────────┘
```

### Security Architecture
```
┌─────────────────────────────────────────────────────┐
│  mTLS (Internal CA + Cert Manager)                  │
├─────────────────────────────────────────────────────┤
│  Vault (Secrets Management)                         │
├─────────────────────────────────────────────────────┤
│  Encryption (AES-256-GCM at rest, TLS 1.3 in transit)│
├─────────────────────────────────────────────────────┤
│  FIPS 140-3 (OpenSSL FIPS Provider)                 │
├─────────────────────────────────────────────────────┤
│  DLP (Data Loss Prevention)                         │
├─────────────────────────────────────────────────────┤
│  Audit Chain (Immutable, tamper-evident)            │
└─────────────────────────────────────────────────────┘
```

### Compliance Frameworks
- **SOC 2** (Type II): Security, Availability, Confidentiality
- **ISO 27001**: ISMS, Risk Management, Continuous Improvement
- **HIPAA**: PHI protection, BAAs, Access Controls
- **PCI DSS**: Cardholder data, Encryption, Access Control
- **GDPR**: Data subject rights, Consent, Breach notification
- **AIDA (Bill C-27)**: AI transparency, Impact assessments
- **EU AI Act**: Risk classification, Conformity assessment
- **NIST AI RMF**: Govern, Map, Measure, Manage framework

## Security

- Never commit secrets or credentials
- Run `make audit` to check for secrets in code
- All API endpoints must have authentication
- Validate and sanitize all user input
- Use `make preflight-check` before production deployment
- Use `make fips-build` for FIPS-compliant deployments
- Use `make airgap-build` for air-gapped environments

## Questions?

Open an issue or contact the team at support@polarisgate.ai
