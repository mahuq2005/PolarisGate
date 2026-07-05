#!/bin/bash
# PolarisGate OPA Initialization Script
# Sets up OPA with prepared queries and data for production latency

set -euo pipefail

echo "=== PolarisGate OPA Initialization ==="

OPA_URL="${OPA_URL:-http://localhost:8181}"
POLICIES_DIR="$(cd "$(dirname "$0")/../../policies" && pwd)"

# Step 1: Create OPA data document with agent permissions
echo "[1/5] Creating OPA data document..."
cat > /tmp/opa_data.json << 'DATAEOF'
{
    "agents": {
        "customer_service": {
            "allowed_tools": ["read_crm", "send_email"],
            "rate_limits": {
                "read_crm": 1000,
                "send_email": 10
            },
            "budget": 500
        },
        "data_analyst": {
            "allowed_tools": ["run_sql", "export_csv"],
            "rate_limits": {
                "run_sql": 100
            },
            "budget": 2000
        },
        "compliance_officer": {
            "allowed_tools": ["read_database", "transfer_funds", "audit_log"],
            "rate_limits": {
                "read_database": 500,
                "transfer_funds": 50,
                "audit_log": 1000
            },
            "budget": 5000
        }
    },
    "models": {
        "llama3.2:1b": {
            "cost_per_token": 0.000001,
            "allowed_teams": ["compliance", "engineering", "customer_service"]
        },
        "llama3.2:3b": {
            "cost_per_token": 0.000003,
            "allowed_teams": ["compliance", "engineering"]
        },
        "gpt-4": {
            "cost_per_token": 0.00003,
            "allowed_teams": ["compliance"]
        }
    },
    "budgets": {
        "compliance": 10000,
        "engineering": 5000,
        "customer_service": 500
    }
}
DATAEOF

curl -s -X PUT "${OPA_URL}/v1/data/polarisgate" \
  -H "Content-Type: application/json" \
  -d @/tmp/opa_data.json > /dev/null
echo "  ✓ Data document loaded"

# Step 2: Load policies
echo "[2/5] Loading OPA policies..."
for policy in "${POLICIES_DIR}"/*.rego; do
    policy_name=$(basename "$policy" .rego)
    echo "  Loading ${policy_name}..."
    curl -s -X PUT "${OPA_URL}/v1/policies/polarisgate/${policy_name}" \
      -H "Content-Type: text/plain" \
      --data-binary @"${policy}" > /dev/null
done
echo "  ✓ All policies loaded"

# Step 3: Create prepared queries for hot paths
echo "[3/5] Creating prepared queries..."
# Cost check query
curl -s -X POST "${OPA_URL}/v1/query/prepare" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "data.polarisgate.cost.allow",
    "name": "cost_check"
  }' > /dev/null

# Tool access query
curl -s -X POST "${OPA_URL}/v1/query/prepare" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "data.polarisgate.agent_tools.allow",
    "name": "tool_access_check"
  }' > /dev/null
echo "  ✓ Prepared queries created"

# Step 4: Test policies
echo "[4/5] Testing OPA policies..."
# Test cost policy
COST_TEST=$(curl -s -X POST "${OPA_URL}/v1/data/polarisgate/cost/allow" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
        "model_id": "llama3.2:1b",
        "team": "compliance",
        "cost_ytd": 5000
    }
  }')
echo "  Cost policy test: ${COST_TEST}"

# Test tool access policy
TOOL_TEST=$(curl -s -X POST "${OPA_URL}/v1/data/polarisgate/agent_tools/allow" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
        "agent": "customer_service",
        "tool": "read_crm"
    }
  }')
echo "  Tool access test: ${TOOL_TEST}"
echo "  ✓ Policies tested"

# Step 5: Enable health checks
echo "[5/5] Enabling OPA health checks..."
curl -s -X PUT "${OPA_URL}/v1/config" \
  -H "Content-Type: application/json" \
  -d '{
    "decision_logs": {
        "console": true
    },
    "status": {
        "console": true
    }
  }' > /dev/null
echo "  ✓ OPA configured"

echo ""
echo "=== OPA Initialization Complete ==="
echo "OPA URL: ${OPA_URL}"
echo "Policies loaded: cost.rego, agent_tools.rego"
echo "Prepared queries: cost_check, tool_access_check"
