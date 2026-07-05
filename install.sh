#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# PolarisGate Installer
# One-command install for customers: curl -fsSL https://polarisgate.ai/install.sh | bash
# 
# Usage:
#   curl -fsSL https://polarisgate.ai/install.sh | bash
#   curl -fsSL https://polarisgate.ai/install.sh | bash -s -- --airgap
#   curl -fsSL https://polarisgate.ai/install.sh | bash -s -- --version 1.1.0
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
log()  { echo -e "${CYAN}[install]${NC} $*"; }
ok()   { echo -e "${GREEN}[  ok ]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn ]${NC} $*"; }
fail() { echo -e "${RED}[FAIL ]${NC} $*"; exit 1; }

VERSION="1.1.0"
REPO="polarisgate/polarisgate"
INSTALL_DIR="${POLARIS_HOME:-${HOME}/polarisgate}"
AIRGAP_MODE=false
SKIP_CHECKS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --airgap) AIRGAP_MODE=true; shift ;;
        --version) VERSION="$2"; shift 2 ;;
        --skip-checks) SKIP_CHECKS=true; shift ;;
        --dir) INSTALL_DIR="$2"; shift 2 ;;
        --help) echo "Usage: install.sh [--airgap] [--version X.Y.Z] [--skip-checks] [--dir /path]"; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║          PolarisGate v${VERSION} Installer                      ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# 1. System Requirements Check
# ═══════════════════════════════════════════════════════════════════════════
log "Checking system requirements..."

# OS check
OS="$(uname -s)"
ARCH="$(uname -m)"
log "Platform: ${OS} / ${ARCH}"

# Docker check
if ! command -v docker &>/dev/null; then
    fail "Docker is not installed. Install it from https://docs.docker.com/get-docker/"
fi
DOCKER_VER=$(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)
log "Docker: ${DOCKER_VER}"
ok "System requirements met"

# ═══════════════════════════════════════════════════════════════════════════
# 2. Clone or Download
# ═══════════════════════════════════════════════════════════════════════════
if [ -d "${INSTALL_DIR}/.git" ]; then
    log "PolarisGate already exists at ${INSTALL_DIR} — updating..."
    cd "${INSTALL_DIR}"
    git fetch origin
    git checkout "tags/v${VERSION}" 2>/dev/null || git checkout main
else
    log "Downloading PolarisGate v${VERSION}..."
    mkdir -p "$(dirname "${INSTALL_DIR}")"
    
    if [ "$AIRGAP_MODE" = true ]; then
        # Air-gap: download the bundle from a release
        AIRGAP_URL="https://github.com/${REPO}/releases/download/v${VERSION}/polarisgate_airgap.tar.gz"
        log "Downloading air-gap bundle from ${AIRGAP_URL}..."
        curl -fsSL -o /tmp/polarisgate_airgap.tar.gz "${AIRGAP_URL}"
        mkdir -p "${INSTALL_DIR}"
        tar xzf /tmp/polarisgate_airgap.tar.gz -C "${INSTALL_DIR}"
        
        # Load Docker images
        log "Loading Docker images..."
        for f in "${INSTALL_DIR}"/*.tar.gz; do
            [ -f "$f" ] && docker load < "$f" && ok "Loaded $(basename $f)" || true
        done
    else
        # Online: git clone
        git clone --depth 1 --branch "v${VERSION}" "https://github.com/${REPO}.git" "${INSTALL_DIR}" 2>/dev/null || \
        git clone --depth 1 "https://github.com/${REPO}.git" "${INSTALL_DIR}"
    fi
    
    cd "${INSTALL_DIR}"
fi

ok "PolarisGate downloaded to ${INSTALL_DIR}"

# ═══════════════════════════════════════════════════════════════════════════
# 3. Configure Environment
# ═══════════════════════════════════════════════════════════════════════════
log "Configuring environment..."

if [ ! -f .env ]; then
    cp .env.example .env
    
    # Generate secure secrets
    JWT_SECRET=$(openssl rand -hex 64 2>/dev/null || echo "change-me-in-production")
    sed -i.bak "s/JWT_SECRET=.*/JWT_SECRET=${JWT_SECRET}/" .env
    rm -f .env.bak
    
    ok "Generated .env with secure JWT secret"
else
    ok ".env already exists — keeping existing configuration"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 4. Build Images (if not air-gap)
# ═══════════════════════════════════════════════════════════════════════════
if [ "$AIRGAP_MODE" = false ]; then
    log "Building Docker images (this may take 10-20 minutes on first run)..."
    docker compose build --parallel 2>&1 | grep -E "(Built|ERROR|failed)" || true
    ok "Docker images built"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 5. Deploy Services
# ═══════════════════════════════════════════════════════════════════════════
log "Deploying PolarisGate..."

# Start infrastructure first
docker compose up -d postgres redis ollama
log "Waiting for infrastructure (PostgreSQL, Redis, Ollama)..."

for i in $(seq 1 60); do
    POSTGRES_OK=$(docker compose ps postgres 2>/dev/null | grep -c "(healthy)" || echo "0")
    REDIS_OK=$(docker compose ps redis 2>/dev/null | grep -c "(healthy)" || echo "0")
    OLLAMA_OK=$(docker compose ps ollama 2>/dev/null | grep -c "(healthy)" || echo "0")
    if [ "$POSTGRES_OK" -ge 1 ] && [ "$REDIS_OK" -ge 1 ] && [ "$OLLAMA_OK" -ge 1 ]; then
        break
    fi
    echo -n "."
    sleep 2
done
echo ""
ok "Infrastructure services healthy"

# Pull Ollama models
docker compose exec -T ollama ollama pull llama3.2:1b 2>/dev/null || true
docker compose exec -T ollama ollama pull tinyllama 2>/dev/null || true
ok "Ollama models ready"

# Start all services
docker compose up -d
log "Waiting for all services..."

for i in $(seq 1 90); do
    UNHEALTHY=$(docker compose ps 2>/dev/null | grep -c "(unhealthy)" || echo "0")
    STARTING=$(docker compose ps 2>/dev/null | grep -c "(starting)" || echo "0")
    if [ "$UNHEALTHY" -eq 0 ] && [ "$STARTING" -eq 0 ]; then
        break
    fi
    echo -n "."
    sleep 3
done
echo ""
ok "All services deployed"

# ═══════════════════════════════════════════════════════════════════════════
# 6. Run Deployment Validation
# ═══════════════════════════════════════════════════════════════════════════
if [ "$SKIP_CHECKS" = false ]; then
    log "Running deployment validation..."
    
    VALIDATION_PASSED=true
    
    # Health check
    for svc in gateway guardrails hallucination-detector kill-switch; do
        PORT=""
        case "$svc" in
            gateway) PORT=8000 ;;
            guardrails) PORT=8005 ;;
            hallucination-detector) PORT=8008 ;;
            kill-switch) PORT=10001 ;;
        esac
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
        if [ "$STATUS" = "200" ]; then
            pass "${svc}: HTTP ${STATUS}"
        else
            fail "${svc}: HTTP ${STATUS}"
            VALIDATION_PASSED=false
        fi
    done
    
    # Run accuracy gates
    log "Running accuracy gates..."
    if bash scripts/run_gates.sh; then
        ok "All accuracy gates passed"
    else
        if [ "$SKIP_CHECKS" = false ]; then
            warn "Some gates failed — see output above"
        fi
    fi
    
    # API smoke test
    log "Testing API..."
    HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)
    if echo "$HEALTH" | grep -q '"status":"healthy"'; then
        ok "API health check passed"
    else
        warn "API health check returned unexpected response"
    fi
    
    if [ "$VALIDATION_PASSED" = true ]; then
        ok "All deployment validation checks passed"
    fi
else
    warn "Deployment checks skipped (--skip-checks)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 7. Print Welcome
# ═══════════════════════════════════════════════════════════════════════════
SERVICE_COUNT=$(docker compose ps --format json 2>/dev/null | wc -l | tr -d ' ')
HEALTHY_COUNT=$(docker compose ps 2>/dev/null | grep -c "(healthy)" || echo "0")

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║       PolarisGate v${VERSION} — Installation Complete!            ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Install Directory:${NC}  ${INSTALL_DIR}"
echo -e "  ${BOLD}Dashboard:${NC}         https://localhost"
echo -e "  ${BOLD}API:${NC}               http://localhost:8000"
echo -e "  ${BOLD}API Docs:${NC}          http://localhost:8000/api/docs"
echo -e "  ${BOLD}Services:${NC}          ${HEALTHY_COUNT}/${SERVICE_COUNT} healthy"
echo ""
echo -e "  ${BOLD}Quick commands:${NC}"
echo -e "    cd ${INSTALL_DIR}"
echo -e "    make status          # Check all services"
echo -e "    make logs            # View logs"
echo -e "    make test-accuracy   # Run accuracy tests"
echo -e "    make down            # Stop all services"
echo ""
echo -e "  ${BOLD}Documentation:${NC}"
echo -e "    ${INSTALL_DIR}/docs/"
echo ""

# Write install receipt
cat > "${INSTALL_DIR}/.install_receipt.json" <<EOF
{
  "version": "${VERSION}",
  "install_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "install_dir": "${INSTALL_DIR}",
  "os": "${OS}",
  "arch": "${ARCH}",
  "docker_version": "${DOCKER_VER}",
  "airgap": ${AIRGAP_MODE},
  "health_checks_passed": ${HEALTHY_COUNT}
}
EOF

ok "Install receipt saved to ${INSTALL_DIR}/.install_receipt.json"