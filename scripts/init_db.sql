-- PolarisGate Database Schema Initialization
-- This file is mounted into PostgreSQL's docker-entrypoint-initdb.d/
-- and runs automatically on first container startup.

-- Traces table
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    prompt TEXT,
    completion TEXT,
    model_id TEXT,
    user_id TEXT,
    tags JSONB,
    timestamp TIMESTAMP
);

-- Guardrail results table
CREATE TABLE IF NOT EXISTS guardrail_results (
    trace_id TEXT PRIMARY KEY,
    toxic BOOLEAN,
    toxic_score FLOAT,
    reason TEXT,
    pii_detected BOOLEAN,
    pii_types TEXT[],
    blocklisted BOOLEAN DEFAULT false,
    injection_detected BOOLEAN DEFAULT false,
    injection_score FLOAT DEFAULT 0.0,
    injection_category VARCHAR(50),
    injection_severity INTEGER DEFAULT 0,
    timestamp TIMESTAMP
);

-- Audit logs table
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
);

-- Feedback table
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    trace_id TEXT,
    model_verdict BOOLEAN,
    client_label BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admin settings table (required for auth setup)
CREATE TABLE IF NOT EXISTS admin_settings (
    id SERIAL PRIMARY KEY,
    admin_email VARCHAR(255) UNIQUE NOT NULL,
    admin_password_hash TEXT NOT NULL,
    session_timeout_minutes INTEGER DEFAULT 30,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Users table (required for LocalAuthProvider JWT + bcrypt auth)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) DEFAULT 'viewer',
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Usage logs table (for token counting and cost tracking)
CREATE TABLE IF NOT EXISTS usage_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    team_id VARCHAR(255) DEFAULT 'default',
    provider VARCHAR(64) NOT NULL,
    model VARCHAR(128) NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON traces (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_traces_model_id ON traces (model_id);
CREATE INDEX IF NOT EXISTS idx_traces_user_id ON traces (user_id);
CREATE INDEX IF NOT EXISTS idx_guardrail_results_timestamp ON guardrail_results (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_guardrail_results_toxic ON guardrail_results (toxic) WHERE toxic = true;
CREATE INDEX IF NOT EXISTS idx_guardrail_results_pii ON guardrail_results (pii_detected) WHERE pii_detected = true;
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_email);
CREATE INDEX IF NOT EXISTS idx_feedback_trace_id ON feedback (trace_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_usage_logs_team_date ON usage_logs (team_id, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_logs_user_date ON usage_logs (user_id, created_at);

-- ── LLM Tool Access Control Tables ──

-- Policy version history (audit trail for policy changes)
CREATE TABLE IF NOT EXISTS tool_policy_versions (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255),
    policy_json JSONB NOT NULL,
    changed_by VARCHAR(255),
    change_summary TEXT,
    approved_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tool call audit log (immutable record of every decision)
CREATE TABLE IF NOT EXISTS tool_call_audit (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255),
    role VARCHAR(50),
    context VARCHAR(50),
    tool_name VARCHAR(255),
    target_resource TEXT,
    result VARCHAR(20) NOT NULL,
    blocked_reason TEXT,
    policy_layer VARCHAR(50),
    latency_ms FLOAT,
    chain_hash VARCHAR(64),
    prev_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Approval queue for human-in-the-loop workflows
CREATE TABLE IF NOT EXISTS tool_approval_queue (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255),
    tool_name VARCHAR(255),
    target_resource TEXT,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    requested_at TIMESTAMP DEFAULT NOW(),
    approved_by VARCHAR(255),
    approved_at TIMESTAMP,
    expires_at TIMESTAMP
);

-- User-specific tool overrides (per-user allow/deny rules)
CREATE TABLE IF NOT EXISTS user_tool_overrides (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255),
    tool_pattern VARCHAR(255),
    target_pattern VARCHAR(255),
    permission VARCHAR(20) NOT NULL,
    reason TEXT,
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_email, tool_pattern, target_pattern)
);

CREATE INDEX IF NOT EXISTS idx_tool_audit_user ON tool_call_audit (user_email, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_audit_result ON tool_call_audit (result);
CREATE INDEX IF NOT EXISTS idx_tool_approval_status ON tool_approval_queue (status);
