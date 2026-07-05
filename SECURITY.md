# Security Policy

## Supported Versions

| Version | Supported          |
|---------|-------------------|
| 1.x.x   | ✅ Active support |

## Reporting a Vulnerability

PolarisGate takes security vulnerabilities seriously. We appreciate your efforts in responsibly disclosing your findings.

### Private Disclosure Process

1. **DO NOT** report security vulnerabilities through public GitHub issues, pull requests, or discussions.
2. Send a detailed report to **security@polarisgate.ai** (or use GitHub's private vulnerability reporting feature).
3. You should receive a response within **48 hours** acknowledging receipt.
4. Our security team will investigate and provide a timeline for fix and disclosure.
5. Once the fix is confirmed, we will:
   - Release a patched version
   - Credit the reporter (unless anonymity is requested)
   - Publish a security advisory on GitHub

### What to Include

Please include the following in your report:
- Type of vulnerability (e.g., XSS, SQL injection, RCE, authentication bypass)
- Full paths of affected source files
- Steps to reproduce (including PoC if possible)
- Impact description
- Any suggested mitigation

### What to Expect

- **Acknowledgement**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Fix timeline**: Typically 7-30 days depending on severity
- **Public disclosure**: After fix is released

## Security Best Practices for Deployments

### Production Checklist

1. **Enable mTLS** (`MTLS_ENABLED=true`) for all inter-service communication
2. **Configure Vault** with a production-grade HA cluster for secrets management
3. **Set `FIPS_MODE=true`** for government or regulated deployments
4. **Use strong secrets** — generate random JWT secrets, API keys, and database passwords
5. **Enable all compliance frameworks** relevant to your jurisdiction
6. **Configure breach notification** email/webhook endpoints
7. **Deploy Prometheus + Alertmanager** for continuous monitoring
8. **Set up log aggregation** (ELK/Loki/Grafana)
9. **Run `make preflight-check`** before deploying to production
10. **Use `Dockerfile.fips`** for FIPS-compliant builds in regulated environments

### Air-Gapped Environments

Use `scripts/build_airgap.sh` to pre-fetch all dependencies for offline deployment.

## Security Features

| Feature | Description |
|---------|-------------|
| mTLS | Mutual TLS for all inter-service communication |
| Encryption at rest | AES-256-GCM field-level encryption |
| Encryption in transit | TLS 1.3 for all HTTP traffic |
| FIPS 140-3 | FIPS-compliant cryptographic operations |
| DLP | Data Loss Prevention with regex/ML content inspection |
| Audit Chain | Immutable, tamper-evident audit logging |
| RBAC | Role-based access control with fine-grained permissions |
| Rate Limiting | Token bucket algorithm per endpoint |
| Input Sanitization | XSS, SQL injection, command injection prevention |
| Secrets Management | HashiCorp Vault integration |
| API Key Management | Scoped API keys with rotation |
| Breach Notification | Automated 72-hour GDPR-compliant notification |
| Circuit Breaker | Compliance-aware circuit breaker for resilience |

## Security Incident Response

For information on our incident response process, see [docs/security/incident_response.md](docs/security/incident_response.md).

## Dependency Scanning

Dependencies are automatically scanned using:
- `pip-audit` — Python dependency vulnerability scanner
- `safety` — Python package vulnerability database
- `trivy` — Container image vulnerability scanner
- `make scan-deps` — Run all dependency scans

## Responsible Disclosure Hall of Fame

We thank the following researchers for responsibly disclosing vulnerabilities:

*This list is intentionally empty until we receive our first report.*

---

*Last updated: 2026-06-28*
*Contact: security@polarisgate.ai*