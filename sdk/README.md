# PolarisGate Python SDK

Python client for the PolarisGate AI Content Safety Gateway.

## Installation

```bash
pip install -e sdk/
```

## Quickstart

```python
from polarisgate import PolarisGate

# Connect (use API key from Settings > API Keys)
pg = PolarisGate(base_url="http://localhost:8002", api_key="pk-...")

# Check content for safety issues
result = pg.check("I hate you, you idiot!")
print(result)
# CheckResult(toxic(0.85))

# Check all flags
print(f"Toxic: {result.toxic}")           # True
print(f"PII: {result.pii_detected}")      # False
print(f"Injection: {result.injection_detected}")  # False
print(f"Blocklisted: {result.blocklisted}")      # False
print(f"Safe: {result.is_safe()}")        # False

# Redact PII from text
safe = pg.redact("My email is john@example.com")
print(safe)  # "My email is j***@***.com"

# Batch check multiple texts
results = pg.check_batch(["Hello world", "I hate you", "john@example.com"])
for r in results:
    print(f"{r.is_safe()}: {r}")

# Stream token-by-token safety results (SSE)
for event in pg.check_stream("hello kill world"):
    print(f"{event['token']}: toxic={event['toxic']}")
# hello: toxic=false
# kill: toxic=true
# world: toxic=false

# Health check
print(pg.health())  # {"status": "ok", "database": "healthy", "redis": "healthy"}
```

## API Reference

### `PolarisGate(base_url, api_key)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | `http://localhost:8002` | Gateway API URL |
| `api_key` | `str` | From env `POLARISGATE_API_KEY` | API key from Settings |

### `pg.check(text: str) -> CheckResult`

Run a full safety check on text content. Returns a `CheckResult` with all detection flags.

### `pg.check_batch(texts: List[str]) -> List[CheckResult]`

Run safety checks on multiple texts in one request.

### `pg.redact(text: str) -> str`

Run a safety check and return the text with PII redacted.

### `pg.check_stream(text: str) -> Generator`

Stream token-by-token safety results via Server-Sent Events (SSE).

### `pg.health() -> Dict`

Check gateway health. Returns database and redis status.

### `CheckResult`

| Field | Type | Description |
|-------|------|-------------|
| `toxic` | `bool` | Toxic content detected |
| `toxic_score` | `float` | Confidence score (0.0-1.0) |
| `reason` | `str` or `None` | Why content was flagged |
| `pii_detected` | `bool` | PII detected |
| `pii_types` | `List[str]` | Types of PII found (EMAIL, PHONE, SIN, etc.) |
| `pii_masked` | `bool` | PII was successfully redacted |
| `redacted_text` | `str` or `None` | Text with PII masked |
| `injection_detected` | `bool` | Prompt injection detected |
| `injection_score` | `float` | Injection confidence (0.0-1.0) |
| `injection_matches` | `int` | Number of patterns matched |
| `blocklisted` | `bool` | Blocklisted words found |
| `_raw` | `dict` | Full API response |

| Method | Returns | Description |
|--------|---------|-------------|
| `is_safe()` | `bool` | True if no safety issues detected |
| `from_response(dict)` | `CheckResult` | Parse from API JSON |

## Context Manager

```python
with PolarisGate(api_key="pk-...") as pg:
    result = pg.check("Hello world")
    print(result.is_safe())
# Auto-closes HTTP session
```

## License

Apache 2.0 — see [LICENSE](../LICENSE)