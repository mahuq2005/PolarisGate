# Gateway API Reference

The PolarisGate Gateway REST API.

## Base URL

```
https://<host>/
http://localhost:8000/   (development)
```

## Authentication

All endpoints except `/health` and `/api/v1/auth/login` require authentication.

### Get Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "polarisgate"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Use Token

Include in Authorization header:
```
Authorization: Bearer <access_token>
```

### Refresh Token

```http
POST /api/v1/auth/refresh
Authorization: Bearer <refresh_token>
```

---

## Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.1.0",
  "services": {
    "postgres": "connected",
    "redis": "connected",
    "ollama": "connected"
  }
}
```

---

## Guardrails

### Run Guardrails Check

```http
POST /api/v1/guardrails/check
Authorization: Bearer <token>
Content-Type: application/json

{
  "text": "Your input text here",
  "checks": ["toxicity", "pii", "sentiment"],
  "context": {
    "domain": "general",
    "user_id": "user-123"
  }
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Input text to analyze |
| `checks` | array | Yes | Checks to run: `toxicity`, `pii`, `sentiment`, `bias` |
| `context` | object | No | Additional context for analysis |

**Response:**
```json
{
  "text": "Your input text here",
  "checks": {
    "toxicity": {
      "score": 0.02,
      "label": "non-toxic",
      "details": {
        "keyword_toxic": false,
        "bert_score": 0.01,
        "roberta_score": 0.03
      }
    },
    "pii": {
      "detected": false,
      "entities": [],
      "risk_score": 0.0
    },
    "sentiment": {
      "label": "positive",
      "score": 0.92
    }
  },
  "timestamp": "2026-06-28T12:00:00Z",
  "request_id": "uuid"
}
```

---

## Hallucination Detection

### Detect Hallucination

```http
POST /api/v1/hallucination/detect
Authorization: Bearer <token>
Content-Type: application/json

{
  "context": "The sky is blue and clouds are white on a sunny day.",
  "response": "The sky is blue.",
  "domain": "general"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `context` | string | Yes | The factual context or source text |
| `response` | string | Yes | The LLM response to evaluate |
| `domain` | string | No | Domain for context-specific thresholds |

**Response:**
```json
{
  "hallucination_score": 0.05,
  "is_hallucination": false,
  "confidence": 0.95,
  "cascade_results": {
    "prefilter": {"score": 0.01, "passed": true},
    "nli": {"score": 0.03, "passed": true},
    "llm_judge": {"score": 0.08, "passed": true}
  },
  "explanation": "The response is factually consistent with the provided context.",
  "request_id": "uuid"
}
```

---

## Compliance

### Generate Compliance Report

```http
GET /api/v1/compliance/report?framework=gdpr&format=pdf
Authorization: Bearer <token>
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `framework` | string | No | Compliance framework: `soc2`, `hipaa`, `gdpr`, `pci`, `eu_ai_act`, `aida` |
| `format` | string | No | Report format: `json`, `pdf`, `html` |

---

## Audit

### Query Audit Logs

```http
GET /api/v1/audit/log?limit=50&offset=0&service=gateway
Authorization: Bearer <token> (admin role required)
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `limit` | integer | No | Results per page (default: 50, max: 1000) |
| `offset` | integer | No | Pagination offset |
| `service` | string | No | Filter by service name |
| `action` | string | No | Filter by action type |
| `actor` | string | No | Filter by actor (user email) |

---

## Agent Governance

### Trigger Kill Switch

```http
POST /api/v1/agent/kill
Authorization: Bearer <token> (admin role required)
Content-Type: application/json

{
  "agent_id": "agent-123",
  "level": "throttle",
  "reason": "Budget exceeded"
}
```

### Get Agent Status

```http
GET /api/v1/agent/status?agent_id=agent-123
Authorization: Bearer <token>
```

### Check Budget

```http
GET /api/v1/budget/status?agent_id=agent-123
Authorization: Bearer <token>
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid request body",
  "errors": [
    {"field": "text", "message": "Field is required"}
  ]
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Insufficient permissions",
  "required_role": "admin"
}
```

### 429 Too Many Requests
```json
{
  "detail": "Rate limit exceeded",
  "retry_after": 30
}
```

### 503 Service Unavailable
```json
{
  "detail": "Service temporarily unavailable",
  "retry_after": 5
}
```

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/api/v1/guardrails/check` | 60 req/min | 1 minute |
| `/api/v1/auth/login` | 30 req/min | 1 minute |
| `/api/v1/auth/*` | 30 req/min | 1 minute |
| All other endpoints | 100 req/min | 1 minute |

Rate limits are configurable via `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW` environment variables.