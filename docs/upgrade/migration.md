# Upgrade & Migration Guide

This guide covers upgrading PolarisGate between versions and migrating data.

## Version Compatibility

| From | To | Breaking Changes | Migration Required |
|------|----|-----------------|-------------------|
| 1.0.0 | 1.1.0 | Yes | Yes |
| 1.1.x | 1.2.x | TBD | TBD |

## Checking Your Version

```bash
# Check current version
curl -s http://localhost:8000/health | jq -r '.version'

# Check changelog for version details
cat CHANGELOG.md
```

## Upgrade Process

### 1. Backup

**Always backup before upgrading:**

```bash
# Database backup
make backup

# Vault backup (if using Vault)
vault operator raft snapshot save vault-backup.snap

# Configuration backup
cp .env .env.backup
cp -r policies/ policies.backup/
```

### 2. Review Breaking Changes

Check the [CHANGELOG.md](../../CHANGELOG.md) for breaking changes between versions.

### 3. Pull Latest Code

```bash
git fetch origin
git checkout tags/v1.1.0  # Or the target version
```

### 4. Update Configuration

```bash
# Review and merge .env changes
diff .env .env.example

# Review policy changes
diff -r policies/ policies.backup/
```

### 5. Run Database Migrations

```bash
make migrate
```

### 6. Rebuild and Deploy

```bash
# Rebuild images
make build

# Restart services
make down
make up

# Verify health
make status
curl -s http://localhost:8000/health | jq .
```

### 7. Verify Migration

```bash
# Run accuracy gates
make test-accuracy

# Verify data integrity
docker compose exec postgres psql -U polarisgate -d polarisgate \
  -c "SELECT COUNT(*) FROM schema_migrations;"

# Check all services are healthy
make polaris-status
```

## Upgrading: 1.0.0 → 1.1.0

### Breaking Changes

1. **Configuration Changes**
   - New required env vars: `MTLS_ENABLED`, `FIPS_MODE`, `DLP_ENABLED`
   - Removed env vars: `SIMPLE_AUTH` (replaced by RBAC)

2. **Database Schema Changes**
   - New tables: `audit_chain`, `data_classification`, `consent_records`
   - New columns: `encryption_key_version` in `users` table

3. **API Changes**
   - `/api/v1/guardrails/check` now requires authentication
   - New response fields in guardrails check: `details`, `request_id`
   - Rate limits introduced on all endpoints

### Migration Steps

```bash
# 1. Backup everything
make backup
cp .env .env.backup

# 2. Update .env with new variables
cat >> .env << EOF
MTLS_ENABLED=false
FIPS_MODE=false
DLP_ENABLED=true
DLP_DEFAULT_ACTION=alert
COMPLIANCE_MODE=full
AUDIT_CHAIN_ENABLED=true
BREACH_NOTIFICATION_ENABLED=true
EOF

# 3. Pull v1.1.0
git pull origin main
# or: git checkout tags/v1.1.0

# 4. Run database migrations
make migrate

# 5. Build and deploy
make build
make down
make up

# 6. Run validation
make test
make test-accuracy
```

### Rollback Plan

If the upgrade fails:

```bash
# 1. Restore backup
git checkout tags/v1.0.0
cp .env.backup .env
make migrate  # Run rollback migrations
make build
make down
make up

# 2. Verify rollback
make test-accuracy
```

## Database Migrations

Migrations are managed via SQL scripts in `scripts/`:

```bash
# Check current migration status
docker compose exec postgres psql -U polarisgate -d polarisgate \
  -c "SELECT version, name, applied_at FROM schema_migrations ORDER BY version;"

# Run pending migrations
make migrate

# Check migration version
docker compose exec postgres psql -U polarisgate -d polarisgate \
  -c "SELECT MAX(version) FROM schema_migrations;"
```

## Data Migration

### Exporting Data

```bash
# Export audit logs
docker compose exec postgres psql -U polarisgate -d polarisgate \
  -c "\COPY (SELECT * FROM audit_log) TO 'audit_export.csv' CSV HEADER"

# Export compliance reports
docker compose exec postgres psql -U polarisgate -d polarisgate \
  -c "\COPY (SELECT * FROM compliance_reports) TO 'compliance_export.csv' CSV HEADER"
```

### Importing Data

```bash
# Import data into new deployment
docker compose exec postgres psql -U polarisgate -d polarisgate \
  -c "\COPY audit_log FROM 'audit_export.csv' CSV HEADER"
```

## Post-Upgrade Validation

### Service Health

```bash
# Check all services
make status

# Check individual service health
for svc in gateway guardrails hallucination-detector; do
  echo "$svc: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health)"
done
```

### Functional Tests

```bash
# Run full test suite
make test

# Run AI/ML tests
make test-aiml

# Run E2E tests
cd tests/e2e && npx playwright test
```

### Security Verification

```bash
# Run security checks
make security-check

# Verify audit chain integrity (if enabled)
make compliance-check
```

## Support

If you encounter issues during upgrade:

1. Check [Troubleshooting Guide](../troubleshooting.md)
2. Search [GitHub Issues](https://github.com/polarisgate/polarisgate/issues)
3. Contact **support@polarisgate.ai**

---

*Last updated: 2026-06-28*
*Maintainer: PolarisGate DevOps Team*