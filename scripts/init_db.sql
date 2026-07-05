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
