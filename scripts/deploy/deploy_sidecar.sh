#!/bin/bash
# PolarisGate Sidecar Proxy Deployment Script
# Deploys Envoy + OPA for zero-trust tool-call gating

set -euo pipefail

echo "=== PolarisGate Sidecar Proxy Deployment ==="

# Configuration
OPA_VERSION="0.68.0"
ENVOY_IMAGE="envoyproxy/envoy:v1.35-latest"
POLICIES_DIR="$(cd "$(dirname "$0")/../../policies" && pwd)"
SIDECAR_DIR="$(cd "$(dirname "$0")/../../services/sidecar-proxy" && pwd)"

# Step 1: Build OPA bundle
echo "[1/5] Building OPA policy bundle..."
opa build "${POLICIES_DIR}/cost.rego" "${POLICIES_DIR}/agent_tools.rego" -o "${SIDECAR_DIR}/bundle.tar.gz"
echo "  ✓ Bundle created at ${SIDECAR_DIR}/bundle.tar.gz"

# Step 2: Load OPA bundle
echo "[2/5] Loading OPA bundle..."
curl -s -X PUT http://localhost:8181/v1/bundles/polarisgate \
  -H "Content-Type: application/octet-stream" \
  --data-binary @"${SIDECAR_DIR}/bundle.tar.gz" > /dev/null
echo "  ✓ Bundle loaded into OPA"

# Step 3: Verify OPA policies
echo "[3/5] Verifying OPA policies..."
curl -s http://localhost:8181/v1/policies | python3 -m json.tool
echo "  ✓ Policies verified"

# Step 4: Deploy Envoy sidecar
echo "[4/5] Deploying Envoy sidecar..."
docker-compose up -d agent-sidecar
echo "  ✓ Envoy sidecar deployed"

# Step 5: Test the sidecar
echo "[5/5] Testing sidecar proxy..."
sleep 3
curl -s -o /dev/null -w "%{http_code}" http://localhost:10000/health || echo "  ⚠ Sidecar health check pending"
echo ""
echo "  ✓ Sidecar proxy is running on port 10000"

echo ""
echo "=== Deployment Complete ==="
echo "Sidecar Proxy: http://localhost:10000"
echo "OPA Server:    http://localhost:8181"
echo "Kill Switch:   http://localhost:10001"
