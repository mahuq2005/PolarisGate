"""Initial PolarisGate schema — consolidates all tables.

Revision ID: 001
Revises: None
Create Date: 2024-01-01 00:00:00

Previously, 12 CREATE TABLE IF NOT EXISTS statements were scattered
across 6 files (main.py lifespan, routers/traces.py, routers/hallucination.py,
routers/misc.py, routers/settings.py, scripts/init_db.sql).

This migration brings them all into a single versioned file.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Core tables ────────────────────────────────────────────────
    op.create_table(
        "admin_settings",
        sa.Column("id", sa.Integer(), primary_key=True, server_default="1"),
        sa.Column("admin_email", sa.Text(), nullable=False),
        sa.Column("admin_password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("email", sa.Text(), primary_key=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), server_default="safety_officer"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("active", sa.Boolean(), server_default=sa.text("TRUE")),
    )

    op.create_table(
        "api_keys",
        sa.Column("key_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), server_default="viewer"),
        sa.Column("created_by", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "webhook_config",
        sa.Column("id", sa.Integer(), primary_key=True, server_default="1"),
        sa.Column("url", sa.Text()),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("events", sa.Text(), server_default="toxicity,pii"),
    )

    op.create_table(
        "traces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt", sa.Text()),
        sa.Column("completion", sa.Text()),
        sa.Column("model_id", sa.Text()),
        sa.Column("user_id", sa.Text()),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "guardrail_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.Integer(), sa.ForeignKey("traces.id")),
        sa.Column("toxic", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("toxic_score", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("reason", sa.Text()),
        sa.Column("pii_detected", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("pii_types", sa.Text()),
        sa.Column("blocklisted", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_email", sa.Text()),
        sa.Column("action", sa.Text()),
        sa.Column("resource_type", sa.Text()),
        sa.Column("resource_id", sa.Text()),
        sa.Column("details", sa.Text()),
        sa.Column("ip_address", sa.Text()),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.Text()),
        sa.Column("model_verdict", sa.Boolean()),
        sa.Column("client_label", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "domain_thresholds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("domain", sa.Text(), nullable=False, unique=True),
        sa.Column("severity", sa.Text(), server_default="medium"),
        sa.Column("toxicity_action", sa.Text(), server_default="flag"),
        sa.Column("pii_action", sa.Text(), server_default="mask"),
    )

    op.create_table(
        "hallucination_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.Text()),
        sa.Column("score", sa.Float()),
        sa.Column("prompt", sa.Text()),
        sa.Column("completion", sa.Text()),
        sa.Column("corrected", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("feedback", sa.Text(), server_default="none"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("hallucination_scores")
    op.drop_table("domain_thresholds")
    op.drop_table("feedback")
    op.drop_table("audit_logs")
    op.drop_table("guardrail_results")
    op.drop_table("traces")
    op.drop_table("webhook_config")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("admin_settings")