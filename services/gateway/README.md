# Gateway Service

The central API gateway for PolarisGate. Handles authentication, authorization, rate limiting, routing, and audit logging.

## Purpose

Acts as the single entry point for all client requests. Routes requests to appropriate backend services, enforces security policies, and maintains audit trails.

## Port

- **Internal**: `8000`
- **External**: `443` (via Nginx reverse proxy)

## API Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/health` | GET | Health check | No |
| `/api/v1/auth/login` | POST | User login | No |
| `/api/v1/auth/verify` | POST | Verify token | Yes |
| `/api/v1/auth/refresh` | POST | Refresh token | Yes |
| `/api/v1/guardrails/check` | POST | Run guardrails checks | Yes |
| `/api/v1/guardrails/health` | GET | Guardrails health | No |
| `/api/v1/hallucination/detect` | POST | Detect hallucination | Yes |
| `/api/v1/compliance/report` | GET | Generate compliance report | Yes |
| `/api/v1/audit/log` | GET | Query audit logs | Yes (admin) |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | (required) | Secret key for JWT signing |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `DATABASE_URL` | `postgresql://polarisgate:polarisgate@postgres:5432/polarisgate` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_REQUESTS` | `100` | Max requests per minute |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `MTLS_ENABLED` | `false` | Enable mTLS |
| `VAULT_ENABLED` | `false` | Enable Vault integration |

## Dependencies

- **PostgreSQL** — Data persistence
- **Redis** — Token blacklist, session cache
- **Guardrails Service** — Toxicity/PII detection
- **Hallucination Detector** — Factual accuracy checks
- **OPA** — Policy evaluation

## Build & Run

```bash
# Build
docker compose build gateway

# Run
docker compose up -d gateway

# View logs
docker compose logs -f gateway

# Run tests
docker compose run --rm tests tests/test_gateway.py
```

## Configuration

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for development setup.
See [docs/deployment/production.md](../../docs/deployment/production.md) for production configuration.