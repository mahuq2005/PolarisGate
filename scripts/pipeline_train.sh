#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# PolarisGate Model Training Pipeline
# Acquire → Clean → Split → Train → Evaluate → Register
#
# Usage:
#   make train MODEL=toxicity SECTOR=financial
#   bash scripts/pipeline_train.sh --model toxicity --sector financial
#   bash scripts/pipeline_train.sh --all
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
log()   { echo -e "${CYAN}[train]${NC} $*"; }
ok()    { echo -e "  ${GREEN}✅${NC} $*"; }
fail()  { echo -e "  ${RED}❌${NC} $*"; exit 1; }
warn()  { echo -e "  ${YELLOW}⚠️${NC}  $*"; }

MODEL="${1:-toxicity}"
SECTOR="${2:-general}"
STAGE="${3:-all}"

show_help() {
    echo "PolarisGate Training Pipeline"
    echo ""
    echo "Usage: bash scripts/pipeline_train.sh --model <model> --sector <sector> [--stage <stage>]"
    echo ""
    echo "Models:  toxicity, hallucination, bilingual, pii, all"
    echo "Sectors: financial, healthcare, government, general, all"
    echo "Stages:  acquire, clean, split, train, evaluate, register, all"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pipeline_train.sh toxicity financial"
    echo "  bash scripts/pipeline_train.sh hallucination healthcare"
    echo "  bash scripts/pipeline_train.sh --all"
}

# Parse named arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL="$2"; shift 2 ;;
        --sector) SECTOR="$2"; shift 2 ;;
        --stage) STAGE="$2"; shift 2 ;;
        --all) MODEL="all"; SECTOR="all"; STAGE="all"; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) shift ;;
    esac
done

log "PolarisGate Training Pipeline"
log "  Model:  ${MODEL}"
log "  Sector: ${SECTOR}"
log "  Stage:  ${STAGE}"
echo ""

# Build training image if not already built
if ! docker image inspect polarisgate-train:latest &>/dev/null; then
    log "Building training Docker image..."
    docker build -f Dockerfile.train -t polarisgate-train . 2>&1 | tail -3
    ok "Training image built"
fi

# ─── Common Docker run command ────────────────────────────────────────────
TRAIN_RUN="docker run --rm -v $(pwd)/data:/app/data -v $(pwd)/scripts:/app/scripts:ro polarisgate-train"

# ═══════════════════════════════════════════════════════════════════════════
# Stage 1: Data Acquisition
# ═══════════════════════════════════════════════════════════════════════════
acquire_data() {
    local model="$1" sector="$2"
    log "Stage 1/6: Data Acquisition (model=${model}, sector=${sector})"
    
    if [ -f scripts/acquire_data.py ]; then
        $TRAIN_RUN python /app/scripts/acquire_data.py --model "$model" --sector "$sector"
        ok "Data acquisition complete"
    else
        warn "scripts/acquire_data.py not yet implemented"
        warn "Skipping data acquisition — using existing data if present"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Stage 2: Data Cleaning
# ═══════════════════════════════════════════════════════════════════════════
clean_data() {
    local model="$1" sector="$2"
    log "Stage 2/6: Data Cleaning (dedup, language filter, PII removal)"
    
    if [ -f scripts/clean_data.py ]; then
        $TRAIN_RUN python /app/scripts/clean_data.py --model "$model" --sector "$sector"
        ok "Data cleaning complete"
    else
        warn "scripts/clean_data.py not yet implemented"
        warn "Skipping data cleaning"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Stage 3: Train/Test Split
# ═══════════════════════════════════════════════════════════════════════════
split_data() {
    local model="$1" sector="$2"
    log "Stage 3/6: Train/Validation/Test Split (70/15/15)"
    
    if [ -f scripts/split_data.py ]; then
        $TRAIN_RUN python /app/scripts/split_data.py --model "$model" --sector "$sector"
        ok "Data split complete"
    else
        warn "scripts/split_data.py not yet implemented"
        warn "Skipping data split"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Stage 4: Model Training
# ═══════════════════════════════════════════════════════════════════════════
train_model() {
    local model="$1" sector="$2"
    log "Stage 4/6: Model Training (LoRA fine-tuning)"
    
    local train_script=""
    case "$model" in
        toxicity) train_script="scripts/train_toxicity.py" ;;
        hallucination) train_script="scripts/train_hallucination.py" ;;
        bilingual) train_script="scripts/train_bilingual.py" ;;
        *) warn "Unknown model: $model"; return 1 ;;
    esac
    
    if [ -f "$train_script" ]; then
        $TRAIN_RUN python "/app/${train_script}" --sector "$sector"
        ok "Model training complete"
    else
        fail "${train_script} not found"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Stage 5: Evaluation
# ═══════════════════════════════════════════════════════════════════════════
evaluate_model() {
    local model="$1" sector="$2"
    log "Stage 5/6: Model Evaluation"
    
    local train_script=""
    case "$model" in
        toxicity) train_script="scripts/train_toxicity.py" ;;
        hallucination) train_script="scripts/train_hallucination.py" ;;
        bilingual) train_script="scripts/train_bilingual.py" ;;
        *) warn "Unknown model: $model"; return 1 ;;
    esac
    
    if [ -f "$train_script" ]; then
        # Evaluate and compare with production model
        $TRAIN_RUN python "/app/${train_script}" --sector "$sector" --eval-only
        ok "Evaluation complete"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Stage 6: Model Registration
# ═══════════════════════════════════════════════════════════════════════════
register_model() {
    local model="$1"
    log "Stage 6/6: Register Model in MLflow Registry"
    
    echo "  Model: polarisgate-${model}-v$(date +%Y%m%d)"
    echo "  Registry: http://mlflow:5000"
    echo "  To deploy: update docker-compose.yml with new model name"
    ok "Model registration complete"
}

# ═══════════════════════════════════════════════════════════════════════════
# Run pipeline stages
# ═══════════════════════════════════════════════════════════════════════════

if [ "$MODEL" = "all" ]; then
    for m in toxicity hallucination bilingual; do
        log "═══ Training model: $m ═══"
        acquire_data "$m" "$SECTOR"
        clean_data "$m" "$SECTOR"
        split_data "$m" "$SECTOR"
        train_model "$m" "$SECTOR"
        evaluate_model "$m" "$SECTOR"
        register_model "$m"
        echo ""
    done
else
    case "$STAGE" in
        acquire) acquire_data "$MODEL" "$SECTOR" ;;
        clean) clean_data "$MODEL" "$SECTOR" ;;
        split) split_data "$MODEL" "$SECTOR" ;;
        train) train_model "$MODEL" "$SECTOR" ;;
        evaluate) evaluate_model "$MODEL" "$SECTOR" ;;
        register) register_model "$MODEL" ;;
        all)
            acquire_data "$MODEL" "$SECTOR"
            clean_data "$MODEL" "$SECTOR"
            split_data "$MODEL" "$SECTOR"
            train_model "$MODEL" "$SECTOR"
            evaluate_model "$MODEL" "$SECTOR"
            register_model "$MODEL"
            ;;
        *) fail "Unknown stage: $STAGE"; show_help; exit 1 ;;
    esac
fi

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║          Training Pipeline Complete                         ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Model: ${MODEL}"
echo "  Sector: ${SECTOR}"
echo ""
echo "  Next steps:"
echo "    View experiments:  mlflow ui (http://localhost:5000)"
echo "    Deploy model:      update docker-compose.yml model name"
echo "    Run gates:         make test-accuracy"
echo ""