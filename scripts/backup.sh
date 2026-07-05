#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# PolarisGate Backup Script
# Enterprise-grade: Encrypted backups with rotation and integrity verification
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/polarisgate}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
ENCRYPTION_KEY="${ENCRYPTION_KEY:-}"
DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${BACKUP_DIR}/backup_${DATE}.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# Create backup directory
mkdir -p "$BACKUP_DIR"

log "Starting PolarisGate backup..."

# ─── PostgreSQL Backup ──────────────────────────────────────────────────
log "Backing up PostgreSQL..."
if docker ps --filter "name=postgres" --format '{{.Names}}' | grep -q postgres; then
    PG_CONTAINER=$(docker ps --filter "name=postgres" --format '{{.Names}}' | head -1)
    PG_USER="${POSTGRES_USER:-truenorth}"
    PG_DB="${POSTGRES_DB:-polarisgate}"
    
    docker exec "$PG_CONTAINER" pg_dump -U "$PG_USER" -d "$PG_DB" --format=custom \
        > "${BACKUP_DIR}/postgres_${DATE}.dump" 2>>"$LOG_FILE"
    
    # Encrypt if key provided
    if [ -n "$ENCRYPTION_KEY" ]; then
        openssl enc -aes-256-cbc -salt -pbkdf2 \
            -in "${BACKUP_DIR}/postgres_${DATE}.dump" \
            -out "${BACKUP_DIR}/postgres_${DATE}.dump.enc" \
            -pass "pass:${ENCRYPTION_KEY}" 2>>"$LOG_FILE"
        rm "${BACKUP_DIR}/postgres_${DATE}.dump"
        log "PostgreSQL backup encrypted: postgres_${DATE}.dump.enc"
    else
        gzip "${BACKUP_DIR}/postgres_${DATE}.dump"
        log "PostgreSQL backup compressed: postgres_${DATE}.dump.gz"
    fi
else
    log "WARNING: PostgreSQL container not found"
fi

# ─── Redis Backup ───────────────────────────────────────────────────────
log "Backing up Redis..."
if docker ps --filter "name=redis" --format '{{.Names}}' | grep -q redis; then
    REDIS_CONTAINER=$(docker ps --filter "name=redis" --format '{{.Names}}' | head -1)
    REDIS_PASSWORD="${REDIS_PASSWORD:-}"
    
    if [ -n "$REDIS_PASSWORD" ]; then
        docker exec "$REDIS_CONTAINER" redis-cli -a "$REDIS_PASSWORD" SAVE 2>>"$LOG_FILE"
    else
        docker exec "$REDIS_CONTAINER" redis-cli SAVE 2>>"$LOG_FILE"
    fi
    
    docker cp "$REDIS_CONTAINER":/data/dump.rdb "${BACKUP_DIR}/redis_${DATE}.rdb" 2>>"$LOG_FILE"
    
    if [ -n "$ENCRYPTION_KEY" ]; then
        openssl enc -aes-256-cbc -salt -pbkdf2 \
            -in "${BACKUP_DIR}/redis_${DATE}.rdb" \
            -out "${BACKUP_DIR}/redis_${DATE}.rdb.enc" \
            -pass "pass:${ENCRYPTION_KEY}" 2>>"$LOG_FILE"
        rm "${BACKUP_DIR}/redis_${DATE}.rdb"
        log "Redis backup encrypted: redis_${DATE}.rdb.enc"
    else
        gzip "${BACKUP_DIR}/redis_${DATE}.rdb"
        log "Redis backup compressed: redis_${DATE}.rdb.gz"
    fi
else
    log "WARNING: Redis container not found"
fi

# ─── Configuration Backup ──────────────────────────────────────────────
log "Backing up configuration..."
tar czf "${BACKUP_DIR}/config_${DATE}.tar.gz" \
    -C "$(dirname "$0")/.." \
    .env.example docker-compose.yml prometheus.yml \
    nginx/polarisgate.conf policies/ 2>>"$LOG_FILE" || true

# ─── Integrity Verification ────────────────────────────────────────────
log "Verifying backup integrity..."
for f in "${BACKUP_DIR}"/*"${DATE}"*; do
    if [ -f "$f" ]; then
        sha256sum "$f" >> "${BACKUP_DIR}/checksums_${DATE}.sha256"
    fi
done
log "Checksums saved: checksums_${DATE}.sha256"

# ─── Retention Cleanup ─────────────────────────────────────────────────
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -type f -mtime "+${RETENTION_DAYS}" -delete 2>>"$LOG_FILE"
find "$BACKUP_DIR" -type f -name "*.log" -mtime "+${RETENTION_DAYS}" -delete 2>>"$LOG_FILE"

# ─── Summary ───────────────────────────────────────────────────────────
BACKUP_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
log "Backup completed successfully"
log "Backup directory: ${BACKUP_DIR}"
log "Total backup size: ${BACKUP_SIZE}"
log "Log file: ${LOG_FILE}"
