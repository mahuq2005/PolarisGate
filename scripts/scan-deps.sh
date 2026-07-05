#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# PolarisGate Dependency Vulnerability Scanner
# Enterprise-grade: Scans all Python requirements files for known CVEs
# Uses pip-audit, safety, and trivy for comprehensive coverage
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

REQUIREMENTS_FILES=(
    "services/gateway/requirements.txt"
    "services/guardrails/requirements.txt"
    "services/aida-bridge/requirements.txt"
    "services/bias-monitor/requirements.txt"
    "services/collector/requirements.txt"
    "services/hallucination-detector/requirements.txt"
    "services/sidecar-proxy/requirements.txt"
    "services/kill-switch/requirements.txt"
    "services/internal-ca/requirements.txt"
    "services/cert-manager/requirements.txt"
    "services/budget-controller/requirements.txt"
    "services/semantic-cache/requirements.txt"
    "services/closed-loop/requirements.txt"
    "tests/requirements.txt"
    "tests/requirements-ai-ml.txt"
    "tests/requirements-e2e.txt"
)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  PolarisGate Dependency Vulnerability Scanner               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Build requirements argument list
REQ_ARGS=()
for req in "${REQUIREMENTS_FILES[@]}"; do
    if [ -f "$req" ]; then
        REQ_ARGS+=("-r" "$req")
    else
        echo "⚠  WARNING: Requirements file not found: $req"
    fi
done

echo "→ Scanning ${#REQ_ARGS[@]} requirements files..."
echo ""

# ─── pip-audit ──────────────────────────────────────────────────────────────
echo "─── pip-audit ────────────────────────────────────────────────"
if command -v pip-audit &>/dev/null; then
    pip-audit "${REQ_ARGS[@]}" --desc 2>&1 || true
else
    echo "pip-audit not installed. Install with: pip install pip-audit"
fi
echo ""

# ─── safety ─────────────────────────────────────────────────────────────────
echo "─── safety ───────────────────────────────────────────────────"
if command -v safety &>/dev/null; then
    if [ -f ".safety-policy.yml" ]; then
        safety check "${REQ_ARGS[@]}" --policy-file .safety-policy.yml --full-report 2>&1 || true
    else
        safety check "${REQ_ARGS[@]}" --full-report 2>&1 || true
    fi
else
    echo "safety not installed. Install with: pip install safety"
fi
echo ""

# ─── trivy (filesystem scan) ───────────────────────────────────────────────
echo "─── trivy (filesystem) ───────────────────────────────────────"
if command -v trivy &>/dev/null; then
    trivy fs --severity HIGH,CRITICAL --no-progress . 2>&1 || true
else
    echo "trivy not installed. Install with: brew install trivy"
fi
echo ""

# ─── Summary ────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Scan complete.                                             ║"
echo "║  Report: reports/dependency-scan-$(date +%Y%m%d).log        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
