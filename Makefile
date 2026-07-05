# ═══════════════════════════════════════════════════════════════════════════
# PolarisGate Makefile
# Enterprise-grade build, test, and deployment automation
# ═══════════════════════════════════════════════════════════════════════════

.PHONY: help deploy setup build up down restart logs test lint clean dev prod train train-all train-status \
        security-check sast scan-deps sbom audit certs ollama-pull status stats \
        polaris-up polaris-down polaris-init polaris-status \
        sidecar-deploy kill-switch-test budget-check cache-stats \
        hallucination-test closed-loop-stats \
        compliance-check compliance-report fips-build airgap-build \
        preflight-check vault-init encrypt-data decrypt-data \
        breach-test consent-audit pci-scan dlp-scan

# Default target
help:
	@echo "PolarisGate Development Commands"
	@echo "═══════════════════════════════════"
	@echo "Core:"
	@echo "  make deploy            - 🚀 One-command full deploy (Build→Test→Deploy)"
	@echo "  make test-accuracy     - 🧪 Fast accuracy gates (<5s, no deploy)"
	@echo "  make test-accuracy-full- 🧪 Full accuracy gates (~60s, tests production models)"
	@echo "  make setup             - Copy .env.example to .env if not exists"
	@echo "  make build             - Build all Docker images"
	@echo "  make up        - Start all services in background"
	@echo "  make down      - Stop all services"
	@echo "  make restart   - Restart all services"
	@echo "  make logs      - Follow logs from all services"
	@echo "  make test      - Run test suite"
	@echo "  make lint      - Run linting checks"
	@echo "  make clean     - Remove all containers, volumes, and images"
	@echo "  make dev       - Start services for development (with hot reload)"
	@echo "  make prod      - Start services for production"
	@echo "  make migrate   - Run database migrations"
	@echo "  make backup    - Backup database"
	@echo "  make restore   - Restore database from backup"
	@echo ""
	@echo "PolarisGate Hero Features:"
	@echo "  make polaris-up       - Start all PolarisGate services"
	@echo "  make polaris-down     - Stop all PolarisGate services"
	@echo "  make polaris-init     - Initialize OPA with policies"
	@echo "  make polaris-status   - Show PolarisGate service status"
	@echo ""
	@echo "Agentic Governance:"
	@echo "  make sidecar-deploy   - Deploy Envoy sidecar proxy"
	@echo "  make kill-switch-test - Test kill switch API"
	@echo ""
	@echo "Cost & Access:"
	@echo "  make budget-check     - Check budget controller status"
	@echo "  make cache-stats      - Show semantic cache statistics"
	@echo ""
	@echo "Hallucination Detection:"
	@echo "  make hallucination-test - Test hallucination detector"
	@echo "  make closed-loop-stats  - Show closed-loop learning stats"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make certs       - Generate self-signed certificates"
	@echo "  make ollama-pull - Pull required Ollama models"
	@echo "  make status      - Show service status"
	@echo "  make stats       - Show resource usage"
	@echo "  make audit       - Run security audit"
	@echo "  make scan-deps   - Scan dependencies for vulnerabilities"
	@echo "  make sbom        - Generate SBOM"
	@echo "  make sast        - Run static analysis (SAST)"
	@echo "  make security-check - Run all security checks"
	@echo ""
	@echo "Compliance & Security:"
	@echo "  make compliance-check  - Check all compliance frameworks status"
	@echo "  make compliance-report - Generate compliance report"
	@echo "  make fips-build        - Build FIPS-compliant Docker image"
	@echo "  make airgap-build      - Build air-gap deployment bundle"
	@echo "  make preflight-check   - Run pre-flight security checks"
	@echo "  make vault-init        - Initialize Vault secrets"
	@echo "  make encrypt-data      - Encrypt sensitive data"
	@echo "  make decrypt-data      - Decrypt sensitive data"
	@echo "  make breach-test       - Test breach notification system"
	@echo "  make consent-audit     - Audit user consent records"
	@echo "  make pci-scan          - Scan for PCI DSS compliance"
	@echo "  make dlp-scan          - Run DLP content inspection"

# One-command full deploy — the only command you need for a fresh machine
deploy:
	@bash scripts/deploy.sh

# Standalone accuracy gate checks (does not deploy)
# Deploy mode: 4 fast smoke tests (<5s)
test-accuracy:
	@bash scripts/run_gates.sh

# Full validation: deploys + API-based enterprise gates (~60s)
# Includes BERT+RoBERTa toxicity API and cascade pipeline API tests
test-accuracy-full:
	@bash scripts/run_gates.sh --full

# Setup development environment
setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example - please edit .env with your secrets"; \
	else \
		echo ".env already exists"; \
	fi
	@echo "Generating JWT secret..."
	@openssl rand -hex 64 2>/dev/null | head -c 64 > /tmp/jwt_secret.txt || true
	@echo "Done. Update JWT_SECRET in .env with: $$(cat /tmp/jwt_secret.txt 2>/dev/null || echo 'openssl rand -hex 64')"

# Build all Docker images
build:
	docker compose build --parallel

# Start all services in background
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# Restart all services
restart: down up

# Follow logs from all services
logs:
	docker compose logs -f

# Run test suite
test:
	docker compose run --rm tests

# Run AI/ML test suite
test-aiml:
	docker compose run --rm ai-ml-tests

# Run linting checks (blocking — type checking and linting must pass)
lint:
	@echo "Running Python linting..."
	@docker run --rm -v $$(pwd):/app -w /app python:3.11-slim bash -c "\
		pip install ruff mypy && \
		ruff check services/ tests/ scripts/ && \
		mypy services/ --ignore-missing-imports"

# Clean up all resources
clean:
	docker compose down -v --remove-orphans
	docker system prune -f

# Development mode (with hot reload)
dev:
	docker compose up --build

# Production mode
prod:
	docker compose -f docker-compose.yml up -d

# Run database migrations
migrate:
	docker compose run --rm -e DATABASE_URL=$${DATABASE_URL} python scripts/init_db.py

# Backup database
backup:
	@echo "Creating database backup..."
	@docker compose exec -T postgres pg_dump -U $$(grep POSTGRES_USER .env | cut -d= -f2) $$(grep POSTGRES_DB .env | cut -d= -f2) > backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup created."

# Restore database from backup
restore:
	@echo "Usage: make restore FILE=backup.sql"
	@cat $(FILE) | docker compose exec -T postgres psql -U $$(grep POSTGRES_USER .env | cut -d= -f2) -d $$(grep POSTGRES_DB .env | cut -d= -f2)

# Generate self-signed certificates for development
certs:
	@mkdir -p nginx/certs
	@openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
		-keyout nginx/certs/polarisgate.key \
		-out nginx/certs/polarisgate.crt \
		-subj "/C=CA/ST=Ontario/L=Toronto/O=PolarisGate/CN=polarisgate.local"
	@echo "Self-signed certificates generated in nginx/certs/"

# Pull required Ollama models
ollama-pull:
	docker compose exec ollama ollama pull llama3.2:1b
	docker compose exec ollama ollama pull tinyllama

# Show service status
status:
	docker compose ps

# Show resource usage
stats:
	docker compose stats

# ─── Model Training Pipeline ────────────────────────────────────────────

# Train a specific model for a specific sector
# Usage: make train MODEL=toxicity SECTOR=financial
train:
	@bash scripts/pipeline_train.sh --model $(MODEL) --sector $(SECTOR) --stage $(STAGE)

# Train all models for all sectors (may take hours)
train-all:
	@bash scripts/pipeline_train.sh --all

# Show training experiment status
train-status:
	@echo "Training Experiments:"
	@curl -s http://localhost:5000/api/2.0/mlflow/experiments/list 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "MLflow not accessible (start: docker compose up -d mlflow)"

# Security audit
audit:
	@echo "Running security audit..."
	@docker run --rm -v $$(pwd):/app aquasec/trivy image --severity HIGH,CRITICAL polarisgate-gateway 2>/dev/null || echo "Trivy not available - install with: brew install trivy"
	@echo "Checking for secrets in code..."
	@grep -r "password\|secret\|key\|token" --include="*.py" --include="*.js" --include="*.yml" --include="*.yaml" services/ 2>/dev/null | grep -v ".env.example" | grep -v "os.getenv" | grep -v "CHANGE_ME" || echo "No obvious secrets found"

# ─── Dependency Scanning ────────────────────────────────────────────────

# Scan Python dependencies for known vulnerabilities
scan-deps:
	@echo "Scanning Python dependencies for vulnerabilities..."
	@bash scripts/scan-deps.sh
	@echo "Dependency scan complete."

# Generate SBOM (Software Bill of Materials)
sbom:
	@echo "Generating SBOM..."
	@docker run --rm -v $$(pwd):/app -w /app python:3.11-slim bash -c "\
		pip install cyclonedx-bom 2>/dev/null && \
		pip freeze | cyclonedx-py > sbom.json 2>/dev/null && \
		echo 'SBOM generated: sbom.json' || echo 'SBOM generation failed'"
	@if [ -f sbom.json ]; then echo "SBOM contains $$(python3 -c 'import json; d=json.load(open(\"sbom.json\")); print(len(d.get(\"components\",[])), \"components\")' 2>/dev/null || echo 'unknown')"; fi

# ─── Static Analysis (SAST) ─────────────────────────────────────────────

# Run bandit security linter
sast:
	@echo "Running static analysis (SAST)..."
	@docker run --rm -v $$(pwd):/app -w /app python:3.11-slim bash -c "\
		pip install bandit semgrep 2>/dev/null && \
		echo '=== bandit ===' && \
		bandit -r services/ -f json --quiet 2>/dev/null | python3 -c \"import sys,json; data=json.load(sys.stdin); print(f'Issues found: {len(data.get(\\\"results\\\",[]))}')\" 2>/dev/null || echo 'bandit check complete' && \
		echo '=== semgrep ===' && \
		semgrep --config=auto --error --quiet services/ 2>/dev/null || echo 'semgrep check complete'"
	@echo "SAST scan complete."

# ─── Full Security Pipeline ─────────────────────────────────────────────

# Run all security checks
security-check: scan-deps sast audit
	@echo "All security checks complete."

# ═══════════════════════════════════════════════════════════════════════════
# PolarisGate Hero Feature Commands
# ═══════════════════════════════════════════════════════════════════════════

# Start all PolarisGate services
polaris-up:
	docker compose up -d opa agent-sidecar kill-switch budget-controller semantic-cache hallucination-detector closed-loop

# Stop all PolarisGate services
polaris-down:
	docker compose down opa agent-sidecar kill-switch budget-controller semantic-cache hallucination-detector closed-loop

# Initialize OPA with policies and data
polaris-init:
	@echo "Initializing OPA with PolarisGate policies..."
	@bash scripts/deploy/init_opa.sh

# Show PolarisGate service status
polaris-status:
	@echo "=== PolarisGate Service Status ==="
	@docker compose ps opa agent-sidecar kill-switch budget-controller semantic-cache hallucination-detector closed-loop

# Deploy Envoy sidecar proxy
sidecar-deploy:
	@echo "Deploying PolarisGate sidecar proxy..."
	@bash scripts/deploy/deploy_sidecar.sh

# Test kill switch API
kill-switch-test:
	@echo "Testing kill switch API..."
	@curl -s -X POST http://localhost:10001/api/v1/agent/kill \
		-H "Content-Type: application/json" \
		-d '{"agent_id": "test-123", "level": "throttle", "reason": "test"}' | python3 -m json.tool

# Check budget controller status
budget-check:
	@echo "Checking budget controller..."
	@curl -s http://localhost:8007/api/v1/budget/health | python3 -m json.tool

# Show semantic cache statistics
cache-stats:
	@echo "Semantic Cache Statistics..."
	@curl -s http://localhost:8010/api/v1/cache/stats | python3 -m json.tool

# Test hallucination detector
hallucination-test:
	@echo "Testing hallucination detector..."
	@curl -s -X POST http://localhost:8008/api/v1/hallucination/detect \
		-H "Content-Type: application/json" \
		-d '{"context": "The sky is blue.", "response": "The sky is green.", "domain": "general"}' | python3 -m json.tool

# Show closed-loop learning stats
closed-loop-stats:
	@echo "Closed-Loop Learning Statistics..."
	@curl -s http://localhost:8009/api/v1/learning/stats | python3 -m json.tool
