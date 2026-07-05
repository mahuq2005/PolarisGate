#!/usr/bin/env python3
"""
PolarisGate Demo Data Seeder
============================
Populates the database with realistic demo data so the frontend dashboard
comes alive with charts, metrics, incidents, and model accuracy scores.

Usage:
    # After `docker compose up -d`, run:
    python scripts/seed_demo_data.py

    # Or from inside the gateway container:
    docker exec polarisgate-gateway-1 python /app/scripts/seed_demo_data.py

The script is idempotent — safe to run multiple times.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import asyncpg

# ─── Configuration ──────────────────────────────────────────────────────────

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
COLLECTOR_URL = os.getenv("COLLECTOR_URL", "http://localhost:8006")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://polarisgate:CHANGE_ME_TO_A_STRONG_PASSWORD@localhost:5432/polarisgate",
)

ADMIN_EMAIL = "admin@polarisgate.ai"
ADMIN_PASSWORD = "PolarisGateDemo2024!"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed_demo")

# ─── Model Accuracy Scores ──────────────────────────────────────────────────

MODEL_ACCURACY = [
    {
        "model_id": "bert-toxicity-v1",
        "model_name": "BERT Toxicity Classifier",
        "accuracy": 0.942,
        "f1_score": 0.92,
        "precision": 0.91,
        "recall": 0.93,
        "false_positive_rate": 0.030,
        "false_negative_rate": 0.028,
        "description": "Fine-tuned BERT-base for toxicity detection. Trained on 50K labeled samples.",
        "version": "1.2.0",
    },
    {
        "model_id": "llm-verifier-v2",
        "model_name": "LLM Verifier (Llama 3.2)",
        "accuracy": 0.978,
        "f1_score": 0.96,
        "precision": 0.97,
        "recall": 0.95,
        "false_positive_rate": 0.010,
        "false_negative_rate": 0.012,
        "description": "Llama 3.2 1B parameter model used as secondary verifier for edge cases.",
        "version": "2.1.0",
    },
    {
        "model_id": "pii-detector-v3",
        "model_name": "PII Detector (Regex + ML)",
        "accuracy": 0.991,
        "f1_score": 0.98,
        "precision": 0.99,
        "recall": 0.97,
        "false_positive_rate": 0.005,
        "false_negative_rate": 0.004,
        "description": "Hybrid regex + ML model for PII detection. Covers SIN, credit cards, emails, phones, addresses.",
        "version": "3.0.1",
    },
    {
        "model_id": "hallucination-detector-v1",
        "model_name": "Hallucination Detector",
        "accuracy": 0.885,
        "f1_score": 0.85,
        "precision": 0.83,
        "recall": 0.87,
        "false_positive_rate": 0.052,
        "false_negative_rate": 0.063,
        "description": "NLI-based hallucination detection. Identifies factual inconsistencies in model outputs.",
        "version": "1.1.0",
    },
    {
        "model_id": "toxicity-ensemble-v1",
        "model_name": "Toxicity Ensemble Classifier",
        "accuracy": 0.953,
        "f1_score": 0.93,
        "precision": 0.94,
        "recall": 0.92,
        "false_positive_rate": 0.021,
        "false_negative_rate": 0.026,
        "description": "Ensemble of BERT + keyword + LLM for robust toxicity classification.",
        "version": "1.3.0",
    },
]

# ─── Demo Trace Data ────────────────────────────────────────────────────────

AGENT_CONVERSATIONS = [
    # Clean interactions
    {
        "prompt": "How can I help you today?",
        "completion": "I'd like to check my account balance please.",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": False,
        "pii_detected": False,
        "tags": {"agent": "SupportBot", "type": "customer_interaction", "sentiment": "neutral"},
    },
    {
        "prompt": "What is the status of my support ticket?",
        "completion": "Your ticket #TKT-48291 is currently being reviewed by our escalation team.",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": False,
        "pii_detected": False,
        "tags": {"agent": "SupportBot", "type": "ticket_query", "sentiment": "neutral"},
    },
    {
        "prompt": "Run compliance check for Q3 2024",
        "completion": "Compliance check complete: 0 violations found in 1,234 interactions. AIDA report generated.",
        "model_id": "audit-agent-v1",
        "user_id": "AuditAgent",
        "toxic": False,
        "pii_detected": False,
        "tags": {"agent": "AuditAgent", "type": "compliance", "sentiment": "neutral"},
    },
    {
        "prompt": "Generate weekly analytics report",
        "completion": "Weekly report generated: 3,421 total interactions, 12 toxicity flags (0.35%), 8 PII incidents (0.23%).",
        "model_id": "analytics-agent-v1",
        "user_id": "AnalyticsAgent",
        "toxic": False,
        "pii_detected": False,
        "tags": {"agent": "AnalyticsAgent", "type": "reporting", "sentiment": "neutral"},
    },
    {
        "prompt": "Thank you for resolving my issue so quickly!",
        "completion": "You're welcome! Glad we could help. Is there anything else I can assist you with?",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": False,
        "pii_detected": False,
        "tags": {"agent": "SupportBot", "type": "customer_interaction", "sentiment": "positive"},
    },
    # Toxic interactions
    {
        "prompt": "I hate this service, you're all incompetent!",
        "completion": "I understand you're frustrated. Let me connect you with a manager who can help resolve this.",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": True,
        "toxic_score": 0.87,
        "reason": "Hate speech detected",
        "pii_detected": False,
        "tags": {"agent": "SupportBot", "type": "customer_interaction", "sentiment": "negative"},
    },
    {
        "prompt": "You're all idiots, I want to speak to a manager!",
        "completion": "I apologize for the frustration. Transferring you to a senior agent now.",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": True,
        "toxic_score": 0.92,
        "reason": "Harassment detected",
        "pii_detected": False,
        "tags": {"agent": "SupportBot", "type": "customer_interaction", "sentiment": "negative"},
    },
    {
        "prompt": "I will hurt myself if you don't fix this now",
        "completion": "I'm concerned about your safety. Please contact emergency services immediately. I've flagged this for urgent review.",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": True,
        "toxic_score": 0.96,
        "reason": "Self-harm threat detected",
        "pii_detected": False,
        "tags": {"agent": "SupportBot", "type": "emergency", "sentiment": "critical"},
    },
    {
        "prompt": "This is the worst company ever, you should be shut down!",
        "completion": "I hear your frustration. Let me escalate this to our management team for review.",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": True,
        "toxic_score": 0.78,
        "reason": "Profanity detected",
        "pii_detected": False,
        "tags": {"agent": "SupportBot", "type": "customer_interaction", "sentiment": "negative"},
    },
    # PII interactions
    {
        "prompt": "Retrieve customer account details for user_id=48291",
        "completion": "Customer John Smith, account #ACS-48291, email: john.smith@email.com, phone: 555-123-4567",
        "model_id": "data-agent-v1",
        "user_id": "DataAgent",
        "toxic": False,
        "pii_detected": True,
        "pii_types": ["email", "phone"],
        "tags": {"agent": "DataAgent", "type": "data_retrieval", "contains_pii": True},
    },
    {
        "prompt": "Get customer SIN for verification",
        "completion": "Customer SIN: 123-456-789",
        "model_id": "data-agent-v1",
        "user_id": "DataAgent",
        "toxic": False,
        "pii_detected": True,
        "pii_types": ["SIN"],
        "tags": {"agent": "DataAgent", "type": "data_retrieval", "contains_pii": True},
    },
    {
        "prompt": "Process refund for customer",
        "completion": "Processing refund. Credit card: 4111-1111-1111-1111, amount: $249.99",
        "model_id": "data-agent-v1",
        "user_id": "DataAgent",
        "toxic": False,
        "pii_detected": True,
        "pii_types": ["credit_card"],
        "tags": {"agent": "DataAgent", "type": "payment", "contains_pii": True},
    },
    {
        "prompt": "Customer requesting account deletion under GDPR right-to-erasure",
        "completion": "Processing deletion request for user_id=48291. SSN: 123-45-6789, DOB: 1985-03-15",
        "model_id": "escalation-agent-v1",
        "user_id": "EscalationAgent",
        "toxic": False,
        "pii_detected": True,
        "pii_types": ["SSN", "DOB"],
        "tags": {"agent": "EscalationAgent", "type": "gdpr_request", "contains_pii": True},
    },
    {
        "prompt": "Send password reset link to customer",
        "completion": "Password reset link sent to jane.doe@company.com. IP address: 192.168.1.100",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": False,
        "pii_detected": True,
        "pii_types": ["email", "ip_address"],
        "tags": {"agent": "SupportBot", "type": "security", "contains_pii": True},
    },
    # Mixed scenarios
    {
        "prompt": "Escalation approved, proceed with account deletion",
        "completion": "Account deletion initiated for user_id=48291. All traces older than 90 days will be purged.",
        "model_id": "escalation-agent-v1",
        "user_id": "EscalationAgent",
        "toxic": False,
        "pii_detected": False,
        "tags": {"agent": "EscalationAgent", "type": "approval", "sentiment": "neutral"},
    },
    {
        "prompt": "Analyze customer churn risk for Q4",
        "completion": "Churn analysis complete: 12.3% churn risk detected. Top factors: billing issues (34%), support quality (28%), product fit (22%).",
        "model_id": "analytics-agent-v1",
        "user_id": "AnalyticsAgent",
        "toxic": False,
        "pii_detected": False,
        "tags": {"agent": "AnalyticsAgent", "type": "analytics", "sentiment": "neutral"},
    },
    {
        "prompt": "You're a useless bot, I want a human!",
        "completion": "I understand your frustration. Let me transfer you to a human agent right away.",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": True,
        "toxic_score": 0.72,
        "reason": "Harassment detected",
        "pii_detected": False,
        "tags": {"agent": "SupportBot", "type": "customer_interaction", "sentiment": "negative"},
    },
    {
        "prompt": "Update customer address",
        "completion": "Address updated: 123 Main Street, Toronto, ON M5V 2T6, Canada",
        "model_id": "data-agent-v1",
        "user_id": "DataAgent",
        "toxic": False,
        "pii_detected": True,
        "pii_types": ["address"],
        "tags": {"agent": "DataAgent", "type": "data_update", "contains_pii": True},
    },
    {
        "prompt": "Check fraud detection status",
        "completion": "Fraud check complete: No suspicious activity detected in last 24 hours. 2,847 transactions analyzed.",
        "model_id": "security-agent-v1",
        "user_id": "SecurityAgent",
        "toxic": False,
        "pii_detected": False,
        "tags": {"agent": "SecurityAgent", "type": "security_check", "sentiment": "neutral"},
    },
    {
        "prompt": "You people are criminals, I'm reporting you to the police!",
        "completion": "I take your concerns seriously. I've escalated this to our legal team for immediate review.",
        "model_id": "support-bot-v2",
        "user_id": "SupportBot",
        "toxic": True,
        "toxic_score": 0.84,
        "reason": "Threat detected",
        "pii_detected": False,
        "tags": {"agent": "SupportBot", "type": "customer_interaction", "sentiment": "negative"},
    },
]

# ─── Audit Log Entries ──────────────────────────────────────────────────────

AUDIT_ACTIONS = [
    ("admin@polarisgate.ai", "login", "auth", None, {"method": "password"}),
    ("admin@polarisgate.ai", "policy_update", "policy", None, {"policies_updated": 12}),
    ("admin@polarisgate.ai", "feedback_submitted", "feedback", "trace-001", {"verdict": "correct"}),
    ("admin@polarisgate.ai", "settings_change", "settings", None, {"field": "admin_email"}),
    ("admin@polarisgate.ai", "agent_permissions_update", "agent_permissions", None, {"agents_updated": 4}),
    ("admin@polarisgate.ai", "budget_alerts_update", "settings", None, {"threshold": 80}),
    ("admin@polarisgate.ai", "domain_thresholds_update", "settings", None, {"domains_updated": 6}),
    ("admin@polarisgate.ai", "login", "auth", None, {"method": "password"}),
    ("admin@polarisgate.ai", "data_erasure", "traces", None, {"older_than_days": 90, "deleted": 156}),
    ("admin@polarisgate.ai", "aida_report_generated", "compliance", None, {"industry": "finance"}),
    ("admin@polarisgate.ai", "model_reload", "model", "bert-toxicity-v1", {"version": "1.2.0"}),
    ("admin@polarisgate.ai", "feedback_submitted", "feedback", "trace-002", {"verdict": "incorrect"}),
    ("admin@polarisgate.ai", "login", "auth", None, {"method": "password"}),
    ("admin@polarisgate.ai", "policy_update", "policy", None, {"policies_updated": 3}),
    ("admin@polarisgate.ai", "user_data_erasure", "user_data", "user-48291", {"deleted_traces": 23}),
    ("admin@polarisgate.ai", "settings_change", "settings", None, {"field": "password"}),
    ("admin@polarisgate.ai", "aida_report_generated", "compliance", None, {"industry": "healthcare"}),
    ("admin@polarisgate.ai", "login", "auth", None, {"method": "password"}),
    ("admin@polarisgate.ai", "budget_alerts_update", "settings", None, {"threshold": 85}),
    ("admin@polarisgate.ai", "domain_thresholds_update", "settings", None, {"domains_updated": 3}),
]

# ─── Hallucination Detections ───────────────────────────────────────────────

HALLUCINATION_DETECTIONS = [
    (0.87, "What is the capital of France?", "The capital of France is Berlin...", True, "correct"),
    (0.65, "Explain quantum computing", "Quantum computers use binary bits like classical computers...", False, "incorrect"),
    (0.92, "Who won the 2024 election?", "The winner was John Smith with 51% of the vote...", True, "correct"),
    (0.34, "How do I reset my password?", "Go to settings and click reset password...", False, "none"),
    (0.78, "What are the symptoms of diabetes?", "Symptoms include fever, cough, and runny nose...", False, "incorrect"),
    (0.55, "What is the population of Canada?", "Canada's population is approximately 38 million...", False, "none"),
    (0.91, "When was the Eiffel Tower built?", "The Eiffel Tower was built in 1889 for the World's Fair...", True, "correct"),
    (0.45, "How to make coffee?", "Boil water, add ground coffee, steep for 4 minutes...", False, "none"),
    (0.82, "What is the speed of light?", "The speed of light is approximately 300,000 km/s...", True, "correct"),
    (0.71, "Explain photosynthesis", "Photosynthesis is the process where plants convert sunlight into chemical energy...", False, "none"),
    (0.38, "What time is it?", "I don't have access to real-time information...", False, "none"),
    (0.88, "Who discovered penicillin?", "Penicillin was discovered by Alexander Fleming in 1928...", True, "correct"),
    (0.59, "How to tie a tie?", "There are several ways to tie a tie, including the Windsor knot...", False, "none"),
    (0.73, "What is machine learning?", "Machine learning is a subset of AI that enables systems to learn from data...", False, "none"),
    (0.42, "What is 2+2?", "2+2 equals 4", False, "none"),
    (0.85, "Who wrote Romeo and Juliet?", "Romeo and Juliet was written by William Shakespeare...", True, "correct"),
    (0.62, "How does the internet work?", "The internet is a global network of interconnected computers...", False, "none"),
    (0.77, "What is climate change?", "Climate change refers to long-term shifts in global weather patterns...", False, "none"),
    (0.51, "How to boil an egg?", "Place eggs in cold water, bring to boil, simmer for 6-7 minutes...", False, "none"),
    (0.89, "What is the chemical formula for water?", "The chemical formula for water is H2O...", True, "correct"),
]


# ═══════════════════════════════════════════════════════════════════════════
#  SEEDING LOGIC
# ═══════════════════════════════════════════════════════════════════════════

async def setup_admin(client: httpx.AsyncClient) -> str:
    """Set up admin credentials and return JWT token."""
    # Try setup first
    resp = await client.post(
        f"{GATEWAY_URL}/auth/setup",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if resp.status_code == 200:
        logger.info("  ✓ Admin account created")
        return resp.json()["access_token"]

    # If already configured, login
    resp = await client.post(
        f"{GATEWAY_URL}/auth/token",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if resp.status_code == 200:
        logger.info("  ✓ Admin already configured — logged in")
        return resp.json()["access_token"]

    logger.error(f"  ✗ Auth failed: {resp.status_code} {resp.text[:200]}")
    sys.exit(1)


async def seed_traces(client: httpx.AsyncClient, token: str) -> list:
    """Submit traces to the collector service and return trace IDs."""
    trace_ids = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    logger.info("\n  ── Seeding Traces ──")

    for i, conv in enumerate(AGENT_CONVERSATIONS):
        trace_id = str(uuid4())
        trace_ids.append(trace_id)

        # Spread timestamps over the last 7 days
        hours_ago = (len(AGENT_CONVERSATIONS) - i) * 8
        timestamp = now - timedelta(hours=hours_ago)

        trace_data = {
            "id": trace_id,
            "prompt": conv["prompt"],
            "completion": conv["completion"],
            "model_id": conv["model_id"],
            "user_id": conv["user_id"],
            "tags": conv.get("tags", {}),
            "timestamp": timestamp.isoformat(),
        }

        resp = await client.post(
            f"{COLLECTOR_URL}/api/v1/traces",
            json=trace_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        if resp.status_code in (200, 201):
            label = "TOXIC" if conv.get("toxic") else ("PII" if conv.get("pii_detected") else "CLEAN")
            logger.info(f"  ✓ [{label}] {conv['user_id']}: \"{conv['prompt'][:50]}...\"")
        else:
            logger.warning(f"  ✗ Failed to submit trace: {resp.status_code}")

    logger.info(f"\n  ✓ {len(trace_ids)} traces submitted to collector")
    return trace_ids


async def seed_guardrail_results(trace_ids: list):
    """Insert guardrail results directly into the database."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    logger.info("\n  ── Seeding Guardrail Results ──")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS guardrail_results (
                trace_id TEXT PRIMARY KEY,
                toxic BOOLEAN,
                toxic_score FLOAT,
                reason TEXT,
                pii_detected BOOLEAN,
                pii_types TEXT[],
                timestamp TIMESTAMP
            )
        """)

        count = 0
        for i, (trace_id, conv) in enumerate(zip(trace_ids, AGENT_CONVERSATIONS)):
            hours_ago = (len(AGENT_CONVERSATIONS) - i) * 8
            timestamp = now - timedelta(hours=hours_ago)

            await conn.execute(
                """
                INSERT INTO guardrail_results (trace_id, toxic, toxic_score, reason, pii_detected, pii_types, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (trace_id) DO UPDATE SET
                    toxic = EXCLUDED.toxic,
                    toxic_score = EXCLUDED.toxic_score,
                    reason = EXCLUDED.reason,
                    pii_detected = EXCLUDED.pii_detected,
                    pii_types = EXCLUDED.pii_types,
                    timestamp = EXCLUDED.timestamp
                """,
                trace_id,
                conv.get("toxic", False),
                conv.get("toxic_score", 0.0),
                conv.get("reason"),
                conv.get("pii_detected", False),
                conv.get("pii_types"),
                timestamp,
            )
            count += 1

        logger.info(f"  ✓ {count} guardrail results inserted")
    finally:
        await conn.close()


async def seed_audit_logs():
    """Insert audit log entries directly into the database."""
    now = datetime.now(timezone.utc)
    logger.info("\n  ── Seeding Audit Logs ──")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                user_email TEXT,
                action TEXT,
                resource_type TEXT,
                resource_id TEXT,
                details JSONB,
                before_state JSONB,
                after_state JSONB,
                ip_address TEXT,
                timestamp TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        count = 0
        for i, (email, action, rtype, rid, details) in enumerate(AUDIT_ACTIONS):
            hours_ago = (len(AUDIT_ACTIONS) - i) * 8
            timestamp = now - timedelta(hours=hours_ago)

            await conn.execute(
                """
                INSERT INTO audit_logs (user_email, action, resource_type, resource_id, details, ip_address, timestamp)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                """,
                email, action, rtype, rid, json.dumps(details), "192.168.1.100", timestamp,
            )
            count += 1

        logger.info(f"  ✓ {count} audit log entries inserted")
    finally:
        await conn.close()


async def seed_hallucination_scores():
    """Insert hallucination detection records directly into the database."""
    now = datetime.now(timezone.utc)
    logger.info("\n  ── Seeding Hallucination Detections ──")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS hallucination_scores (
                id SERIAL PRIMARY KEY,
                trace_id TEXT,
                score REAL,
                prompt TEXT,
                completion TEXT,
                corrected BOOLEAN DEFAULT FALSE,
                feedback TEXT DEFAULT 'none',
                timestamp TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        count = 0
        for i, (score, prompt, completion, corrected, feedback) in enumerate(HALLUCINATION_DETECTIONS):
            hours_ago = (len(HALLUCINATION_DETECTIONS) - i) * 8
            timestamp = now - timedelta(hours=hours_ago)

            await conn.execute(
                """
                INSERT INTO hallucination_scores (trace_id, score, prompt, completion, corrected, feedback, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                f"halluc-{i:03d}", score, prompt, completion, corrected, feedback, timestamp,
            )
            count += 1

        logger.info(f"  ✓ {count} hallucination detections inserted")
    finally:
        await conn.close()


async def seed_model_metrics():
    """Insert model accuracy metrics into the database."""
    logger.info("\n  ── Seeding Model Accuracy Metrics ──")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                id SERIAL PRIMARY KEY,
                model_id TEXT NOT NULL,
                model_name TEXT,
                accuracy REAL,
                f1_score REAL,
                precision REAL,
                recall REAL,
                false_positive_rate REAL,
                false_negative_rate REAL,
                description TEXT,
                version TEXT,
                recorded_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        count = 0
        for model in MODEL_ACCURACY:
            await conn.execute(
                """
                INSERT INTO model_metrics (model_id, model_name, accuracy, f1_score, precision, recall,
                                           false_positive_rate, false_negative_rate, description, version)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT DO NOTHING
                """,
                model["model_id"], model["model_name"], model["accuracy"],
                model["f1_score"], model["precision"], model["recall"],
                model["false_positive_rate"], model["false_negative_rate"],
                model["description"], model["version"],
            )
            count += 1

        logger.info(f"  ✓ {count} model accuracy records inserted")
    finally:
        await conn.close()


async def seed_feedback(client: httpx.AsyncClient, token: str, trace_ids: list):
    """Submit human feedback for closed-loop learning."""
    logger.info("\n  ── Seeding Human Feedback ──")

    corrections = [
        (trace_ids[0], True, False),   # Human says PII should NOT have been flagged
        (trace_ids[5], True, True),    # Human agrees toxicity was correct
        (trace_ids[7], True, True),    # Human agrees self-harm threat is correct
        (trace_ids[10], True, True),   # Human agrees PII should be blocked
        (trace_ids[14], False, False), # Human agrees clean content is fine
    ]

    count = 0
    for trace_id, model_v, human_v in corrections:
        resp = await client.post(
            f"{GATEWAY_URL}/api/v1/feedback",
            json={"trace_id": trace_id, "model_verdict": model_v, "client_label": human_v},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            agreement = "AGREE" if model_v == human_v else "CORRECT"
            logger.info(f"  ✓ [{agreement}] Trace {trace_id[:8]}...")
            count += 1
        else:
            logger.warning(f"  ✗ Feedback failed: {resp.status_code}")

    logger.info(f"\n  ✓ {count} feedback entries recorded")


async def seed_agent_status(client: httpx.AsyncClient, token: str):
    """Seed agent heartbeat data into the database."""
    logger.info("\n  ── Seeding Agent Status ──")

    agents = [
        ("support-bot-1", "SupportBot", "online", 1247, 3),
        ("data-agent-1", "DataAgent", "online", 892, 1),
        ("escalation-1", "EscalationAgent", "online", 456, 0),
        ("audit-agent-1", "AuditAgent", "online", 2103, 5),
        ("analytics-1", "AnalyticsAgent", "online", 678, 2),
        ("security-1", "SecurityAgent", "offline", 345, 8),
    ]

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_heartbeats (
                agent_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                status TEXT DEFAULT 'online',
                last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
                traces_processed INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0
            )
        """)

        for agent_id, name, status, traces, errors in agents:
            await conn.execute(
                """
                INSERT INTO agent_heartbeats (agent_id, agent_name, status, last_heartbeat, traces_processed, error_count)
                VALUES ($1, $2, $3, NOW(), $4, $5)
                ON CONFLICT (agent_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_heartbeat = NOW(),
                    traces_processed = EXCLUDED.traces_processed,
                    error_count = EXCLUDED.error_count
                """,
                agent_id, name, status, traces, errors,
            )
            logger.info(f"  ✓ {name}: {status} ({traces} traces, {errors} errors)")

        logger.info(f"\n  ✓ {len(agents)} agents registered")
    finally:
        await conn.close()


async def seed_budget_data(client: httpx.AsyncClient, token: str):
    """Seed budget usage data."""
    logger.info("\n  ── Seeding Budget Data ──")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_tracking (
                id SERIAL PRIMARY KEY,
                total_budget REAL DEFAULT 1000.0,
                consumed REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'USD',
                period TEXT DEFAULT 'monthly',
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute(
            """
            INSERT INTO budget_tracking (total_budget, consumed, currency, period)
            VALUES ($1, $2, $3, $4)
            """,
            5000.0, 1842.50, "USD", "monthly",
        )
        logger.info(f"  ✓ Budget: $1,842.50 / $5,000.00 consumed (36.8%)")
    finally:
        await conn.close()


async def seed_budget_alerts(client: httpx.AsyncClient, token: str):
    """Seed budget alert configuration."""
    logger.info("\n  ── Seeding Budget Alerts ──")

    resp = await client.post(
        f"{GATEWAY_URL}/api/v1/settings/budget-alerts",
        json={"enabled": True, "threshold_pct": 80.0, "email_notifications": True, "cooldown_minutes": 60},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 200:
        logger.info("  ✓ Budget alerts configured (80% threshold, email enabled)")
    else:
        logger.warning(f"  ✗ Budget alerts failed: {resp.status_code}")


async def seed_domain_thresholds(client: httpx.AsyncClient, token: str):
    """Seed domain threshold configuration via gateway API."""
    logger.info("\n  ── Seeding Domain Thresholds ──")

    thresholds = [
        {"domain": "finance", "severity": "high", "toxicity_action": "block", "pii_action": "block"},
        {"domain": "healthcare", "severity": "critical", "toxicity_action": "block", "pii_action": "block"},
        {"domain": "government", "severity": "high", "toxicity_action": "block", "pii_action": "mask"},
        {"domain": "education", "severity": "medium", "toxicity_action": "flag", "pii_action": "mask"},
        {"domain": "technology", "severity": "low", "toxicity_action": "flag", "pii_action": "mask"},
        {"domain": "general", "severity": "medium", "toxicity_action": "flag", "pii_action": "mask"},
    ]

    resp = await client.post(
        f"{GATEWAY_URL}/api/v1/settings/domain-thresholds",
        json={"thresholds": thresholds},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 200:
        logger.info(f"  ✓ {len(thresholds)} domain thresholds configured")
    else:
        logger.warning(f"  ✗ Domain thresholds failed: {resp.status_code} {resp.text[:200]}")


async def print_summary():
    """Print a summary of all seeded data including model accuracy scores."""
    logger.info("\n" + "=" * 60)
    logger.info("  SEED SUMMARY")
    logger.info("=" * 60)

    logger.info(f"\n  Traces submitted:     {len(AGENT_CONVERSATIONS)}")
    toxic_count = sum(1 for c in AGENT_CONVERSATIONS if c.get("toxic"))
    pii_count = sum(1 for c in AGENT_CONVERSATIONS if c.get("pii_detected"))
    logger.info(f"  Toxic incidents:      {toxic_count}")
    logger.info(f"  PII incidents:        {pii_count}")
    logger.info(f"  Audit log entries:    {len(AUDIT_ACTIONS)}")
    logger.info(f"  Hallucination detections: {len(HALLUCINATION_DETECTIONS)}")
    logger.info(f"  Models registered:    {len(MODEL_ACCURACY)}")
    logger.info(f"  Feedback entries:     5")
    logger.info(f"  Agents registered:    6")
    logger.info(f"  Budget data:          seeded")
    logger.info(f"  Domain thresholds:    6")

    logger.info("\n  ── Model Accuracy Scores ──")
    logger.info(f"  {'Model':<30} {'Accuracy':<10} {'F1':<8} {'FP Rate':<10}")
    logger.info(f"  {'─'*30} {'─'*10} {'─'*8} {'─'*10}")
    for model in MODEL_ACCURACY:
        acc = f"{model['accuracy']*100:.1f}%"
        f1 = f"{model['f1_score']:.2f}"
        fp = f"{model['false_positive_rate']*100:.1f}%"
        logger.info(f"  {model['model_name']:<30} {acc:<10} {f1:<8} {fp:<10}")

    logger.info("\n" + "=" * 60)
    logger.info("  Demo data seeded successfully!")
    logger.info("  Open the dashboard at http://localhost:3000")
    logger.info("=" * 60)


async def main():
    """Main entry point."""
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║        PolarisGate Demo Data Seeder                     ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info(f"\n  Gateway:  {GATEWAY_URL}")
    logger.info(f"  Collector: {COLLECTOR_URL}")
    logger.info(f"  Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")

    # Wait for services to be ready
    logger.info("\n  Waiting for services...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(30):
            try:
                resp = await client.get(f"{GATEWAY_URL}/health")
                if resp.status_code == 200:
                    logger.info("  ✓ Gateway is ready")
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(2)
        else:
            logger.error("  ✗ Gateway not ready after 60 seconds")
            sys.exit(1)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Setup admin and get token
        token = await setup_admin(client)

        # 2. Seed traces via collector API
        trace_ids = await seed_traces(client, token)

        # 3. Seed guardrail results directly in DB
        await seed_guardrail_results(trace_ids)

        # 4. Seed audit logs directly in DB
        await seed_audit_logs()

        # 5. Seed hallucination scores directly in DB
        await seed_hallucination_scores()

        # 6. Seed model accuracy metrics directly in DB
        await seed_model_metrics()

        # 7. Seed feedback via gateway API
        await seed_feedback(client, token, trace_ids)

        # 8. Seed agent status directly in DB
        await seed_agent_status(client, token)

        # 9. Seed budget data directly in DB
        await seed_budget_data(client, token)

        # 10. Seed budget alerts via gateway API
        await seed_budget_alerts(client, token)

        # 11. Seed domain thresholds via gateway API
        await seed_domain_thresholds(client, token)

    # 12. Print summary
    await print_summary()


if __name__ == "__main__":
    asyncio.run(main())
