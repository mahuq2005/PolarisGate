# Changelog

## [1.1.0] - 2026-06-18

### Added
- **FIPS 140-3 Compliance**: FIPS-compliant Dockerfile with OpenSSL FIPS provider, cryptography 42.0.5, pyopenssl 24.1.0
- **mTLS Infrastructure**: Internal Certificate Authority (internal-ca), Cert Manager for automated certificate lifecycle
- **Sidecar Proxy**: Envoy-based sidecar proxy for agent governance with mTLS termination
- **Kill Switch**: Agent kill switch service with throttle/stop/isolate levels
- **Vault Integration**: HashiCorp Vault for secrets management with auto-unseal
- **Encryption Module**: AES-256-GCM encryption at rest, TLS 1.3 in transit
- **Audit Chain**: Immutable, tamper-evident audit logging with cryptographic chaining
- **Data Classification**: Automated data classification (public/internal/confidential/restricted)
- **DLP Engine**: Data Loss Prevention with regex/ML-based content inspection
- **PCI DSS Module**: Credit card data detection, encryption, access control
- **Consent Management**: User consent tracking with GDPR/AIDA compliance
- **Breach Notification**: Automated breach detection and notification workflow
- **RBAC**: Role-based access control with fine-grained permissions
- **API Key Management**: Scoped API key authentication with rotation
- **Input Sanitizer**: Comprehensive input sanitization (XSS, SQLi, command injection)
- **Session Management**: Secure session handling with rotation and timeout
- **Pre-flight Checks**: Pre-deployment security validation
- **Semgrep Rules**: Custom AI governance SAST rules (10 rules covering AI safety, PII, compliance, security)
- **Enhanced Pre-commit**: 20+ pre-commit hooks including hadolint, yamllint, safety
- **Enhanced Dependency Scanning**: 16 requirements files scanned with pip-audit + safety + trivy
- **Air-Gap Bundle**: Enhanced air-gap build with SBOM, policies, compliance docs
- **Compliance Dashboard**: Frontend compliance framework status visualization
- **Security Settings UI**: Frontend security configuration panel
- **Audit Log Viewer**: Frontend audit log browsing with filtering
- **Breach Notification UI**: Frontend breach notification management
- **Consent Manager UI**: Frontend user consent management interface
- **Compliance Documentation**: Full docs for SOC 2, ISO 27001, HIPAA, PCI DSS, GDPR, AIDA, EU AI Act, NIST AI RMF
- **Security Architecture Documentation**: Comprehensive security architecture guide
- **Incident Response Plan**: Documented incident response procedures
- **Data Flow Diagrams**: Architecture diagrams for data flows and security controls

### Enhanced
- **Makefile**: 30+ targets including compliance-check, fips-build, airgap-build, preflight-check
- **Bandit Config**: Enhanced with plugin-specific skip rules
- **Safety Policy**: Added fail-build thresholds and report configuration
- **Prometheus Alerts**: 15+ alerting rules for security, performance, and compliance
- **Load Testing**: k6-based load tests with comprehensive scenarios
- **Backup Script**: Enhanced with encryption and rotation
- **Autoscaler**: HPA-based autoscaler with custom metrics
- **Nginx Config**: Enhanced with WAF rules, rate limiting, security headers
- **K8s Deployment**: Enhanced with security contexts, pod security policies, resource limits
- **Helm Values**: Comprehensive values with all security configurations

### Security
- FIPS 140-3 validated cryptography
- mTLS for all inter-service communication
- AES-256-GCM encryption at rest
- TLS 1.3 in transit
- Immutable audit chain
- Automated breach notification
- DLP content inspection
- PCI DSS Level 1 compliance
- SOC 2 Type II readiness
- ISO 27001 ISMS alignment
- HIPAA Privacy Rule compliance
- GDPR data subject rights
- AIDA (Bill C-27) compliance
- EU AI Act conformity
- NIST AI RMF framework alignment

## [1.0.0] - 2026-06-09

### Added
- Initial release of PolarisGate AI Governance Platform
- Multi-tier toxicity detection (keyword → BERT → LLM)
- PII detection with Luhn validation (SIN, credit cards, health cards, etc.)
- Configurable policy engine with NIST AI RMF alignment
- JWT-based authentication with token refresh and revocation
- Redis-backed token blacklist with in-memory fallback
- Rate limiting on all API endpoints
- Structured JSON logging with OpenTelemetry tracing
- Prometheus metrics for monitoring
- AIDA (Bill C-27) compliance reporting with PDF generation
- SHAP explainability for model interpretability
- Bias monitoring and fairness scoring
- Adaptive model selection with fallback
- Incident escalation with webhook notifications
- Right-to-erasure endpoints (GDPR/AIDA compliance)
- Audit logging with before/after state tracking
- Data retention policy with auto-cleanup
- NIST MAP 2.2 Risk Impact Assessment
- MEASURE 3.1 Bias Testing Framework
- Protected attribute collection for fairness analysis
- PII masking in audit logs
- Input sanitization on all user-facing endpoints
- Shared BERT model manager for resource efficiency
- Model registry with versioning, drift detection, and A/B testing
- Docker Compose deployment with health checks
- Kubernetes Helm charts for production
- Comprehensive test suite (unit, integration, AI/ML, E2E)
- Security scanning (SAST, dependency audit, SBOM)

### Security
- All secrets from environment variables only
- bcrypt password hashing with salt
- CORS restricted to specific origins
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
