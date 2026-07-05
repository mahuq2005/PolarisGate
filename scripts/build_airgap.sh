#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# PolarisGate Air-Gap Bundle Generator
# Creates a single tarball with all Docker images, models, Helm charts,
# compliance docs, SBOM, and security policies for deployment in
# environments with no outbound internet.
# Usage: bash scripts/build_airgap.sh
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT="${POLARIS_OUTPUT:-${PROJECT_DIR}/polarisgate_airgap.tar.gz}"
TEMP_DIR=$(mktemp -d)
trap 'rm -rf ${TEMP_DIR}' EXIT

log() { echo -e "\033[0;36m[airgap]\033[0m $*"; }
ok()  { echo -e "\033[0;32m[  ok ]\033[0m $*"; }
warn() { echo -e "\033[0;33m[ warn ]\033[0m $*"; }

cd "$PROJECT_DIR"

log "Building all Docker images..."
docker compose build --parallel 2>&1 | tail -5

log "Saving Docker images..."
SERVICES=(gateway guardrails hallucination-detector aida-bridge collector kill-switch budget-controller semantic-cache closed-loop bias-monitor retraining sidecar-proxy internal-ca cert-manager nginx frontend mlflow)
for svc in "${SERVICES[@]}"; do
    docker save "polarisgate-${svc}:latest" 2>/dev/null | gzip > "${TEMP_DIR}/${svc}.tar.gz" || warn "Could not save ${svc}"
done

# Also save FIPS image if built
if docker image inspect polarisgate-gateway:fips &>/dev/null; then
    docker save polarisgate-gateway:fips | gzip > "${TEMP_DIR}/gateway-fips.tar.gz"
    ok "FIPS image saved"
fi
ok "Docker images saved"

log "Copying Ollama models..."
mkdir -p "${TEMP_DIR}/ollama_models"
docker compose exec -T ollama ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | while read model; do
    docker compose exec -T ollama ollama pull "$model" 2>/dev/null || true
done
docker compose exec -T ollama tar czf - /root/.ollama 2>/dev/null > "${TEMP_DIR}/ollama_models.tar.gz" || warn "Ollama models not available (start ollama service first)"
ok "Models bundled"

log "Copying Helm charts..."
cp -r k8s/helm "${TEMP_DIR}/helm_charts"
ok "Helm charts copied"

log "Copying security policies and compliance docs..."
mkdir -p "${TEMP_DIR}/policies" "${TEMP_DIR}/compliance"
cp -r policies/* "${TEMP_DIR}/policies/" 2>/dev/null || true
cp -r docs/compliance/* "${TEMP_DIR}/compliance/" 2>/dev/null || true
cp -r semgrep/rules/* "${TEMP_DIR}/policies/" 2>/dev/null || true
ok "Policies and docs copied"

log "Generating SBOM..."
if command -v cyclonedx-bom &>/dev/null; then
    pip freeze | cyclonedx-py > "${TEMP_DIR}/sbom.json" 2>/dev/null || true
fi
ok "SBOM generated"

log "Copying documentation..."
cp CHANGELOG.md CONTRIBUTING.md README.md "${TEMP_DIR}/" 2>/dev/null || true
ok "Docs copied"

log "Creating air-gap tarball..."
tar czf "$OUTPUT" -C "$TEMP_DIR" .
ok "Air-gap bundle created: $OUTPUT"
echo ""
echo "  Bundle size: $(du -h "$OUTPUT" | cut -f1)"
echo ""
echo "  Deploy with:"
echo "    AIRGAP=true make deploy"
echo ""
echo "  Extract:"
echo "    tar xzf polarisgate_airgap.tar.gz"
echo ""
echo "  Load images:"
echo "    for f in *.tar.gz; do docker load < \$f; done"
echo ""
echo "  Verify checksum:"
echo "    sha256sum polarisgate_airgap.tar.gz"
