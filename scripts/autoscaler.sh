#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# PolarisGate HPA-based Autoscaler
# Enterprise-grade: Horizontal Pod Autoscaler with custom metrics
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Configuration
NAMESPACE="${NAMESPACE:-polarisgate}"
MIN_REPLICAS="${MIN_REPLICAS:-2}"
MAX_REPLICAS="${MAX_REPLICAS:-10}"
CPU_THRESHOLD="${CPU_THRESHOLD:-70}"
MEMORY_THRESHOLD="${MEMORY_THRESHOLD:-80}"
TARGET_SERVICE="${TARGET_SERVICE:-guardrails}"

log() { echo -e "\033[0;36m[autoscaler]\033[0m $*"; }
warn() { echo -e "\033[0;33m[autoscaler]\033[0m $*"; }

# Check if running in Kubernetes
if command -v kubectl &>/dev/null && kubectl config current-context &>/dev/null 2>&1; then
    log "Running in Kubernetes mode"
    
    # Apply HPA configuration
    cat <<EOF | kubectl apply -f -
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: polarisgate-${TARGET_SERVICE}
  namespace: ${NAMESPACE}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: polarisgate-${TARGET_SERVICE}
  minReplicas: ${MIN_REPLICAS}
  maxReplicas: ${MAX_REPLICAS}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: ${CPU_THRESHOLD}
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: ${MEMORY_THRESHOLD}
  - type: Pods
    pods:
      metric:
        name: guardrail_latency_p99
      target:
        type: AverageValue
        averageValue: 2.0
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 4
        periodSeconds: 15
      selectPolicy: Max
EOF
    log "HPA applied for ${TARGET_SERVICE}"
    
else
    log "Running in Docker Compose mode"
    
    # Docker Compose autoscaling
    while true; do
        CPU_SUM=0
        COUNT=0
        
        for CONTAINER in $(docker ps --filter "name=${TARGET_SERVICE}" -q); do
            CPU=$(docker stats --no-stream --format '{{.CPUPerc}}' "$CONTAINER" | sed 's/%//')
            if [ -n "$CPU" ]; then
                CPU_SUM=$(echo "$CPU_SUM + $CPU" | bc 2>/dev/null || echo 0)
                COUNT=$((COUNT + 1))
            fi
        done
        
        if [ "$COUNT" -gt 0 ]; then
            AVG_CPU=$(echo "scale=2; $CPU_SUM / $COUNT" | bc 2>/dev/null || echo 0)
            log "Average CPU for ${TARGET_SERVICE}: ${AVG_CPU}%"
            
            if [ "$(echo "$AVG_CPU > $CPU_THRESHOLD" | bc 2>/dev/null || echo 0)" -eq 1 ]; then
                NEW_COUNT=$((COUNT * 2))
                [ "$NEW_COUNT" -gt "$MAX_REPLICAS" ] && NEW_COUNT=$MAX_REPLICAS
                log "High CPU, scaling ${TARGET_SERVICE} to ${NEW_COUNT}"
                docker compose up --scale "${TARGET_SERVICE}=${NEW_COUNT}" -d
            elif [ "$(echo "$AVG_CPU < 30" | bc 2>/dev/null || echo 0)" -eq 1 ]; then
                NEW_COUNT=$((COUNT / 2))
                [ "$NEW_COUNT" -lt "$MIN_REPLICAS" ] && NEW_COUNT=$MIN_REPLICAS
                log "Low CPU, scaling ${TARGET_SERVICE} to ${NEW_COUNT}"
                docker compose up --scale "${TARGET_SERVICE}=${NEW_COUNT}" -d
            else
                log "CPU normal, no scaling needed"
            fi
        fi
        
        sleep 30
    done
fi
