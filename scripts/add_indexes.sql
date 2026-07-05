-- PolarisGate Database Migration
-- Adds tables for kill switch, budget tracking, hallucination corrections,
-- semantic cache stats, and agent permissions

-- ============================================================
-- 1. Agent Runs (Kill Switch State)
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY,
    agent_name TEXT NOT NULL,
    agent_type TEXT DEFAULT 'unknown',
    state TEXT NOT NULL DEFAULT 'running',  -- 'running', 'throttled', 'paused', 'stopped', 'recovering'
    last_checkpoint JSONB,
    kill_reason TEXT,
    stopped_by TEXT,
    stopped_at TIMESTAMPTZ,
    resumed_at TIMESTAMPTZ,
    audit_hash TEXT,  -- SHA256 of run log for immutability
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_state ON agent_runs(state);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_name ON agent_runs(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at ON agent_runs(created_at);

-- ============================================================
-- 2. Budget Tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS budget_tracking (
    id SERIAL PRIMARY KEY,
    team TEXT NOT NULL,
    model_id TEXT NOT NULL,
    cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    token_count BIGINT NOT NULL DEFAULT 0,
    request_count BIGINT NOT NULL DEFAULT 0,
    budget_limit DOUBLE PRECISION NOT NULL DEFAULT 100,
    period TEXT NOT NULL DEFAULT 'monthly',  -- 'daily', 'weekly', 'monthly'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_budget_tracking_team ON budget_tracking(team);
CREATE INDEX IF NOT EXISTS idx_budget_tracking_period ON budget_tracking(period_start, period_end);
CREATE UNIQUE INDEX IF NOT EXISTS idx_budget_tracking_unique 
    ON budget_tracking(team, model_id, period, period_start);

-- ============================================================
-- 3. Hallucination Corrections (Closed-Loop Learning)
-- ============================================================
CREATE TABLE IF NOT EXISTS hallucination_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id TEXT,
    context TEXT,
    response TEXT,
    llm_verdict BOOLEAN,  -- True = hallucination flagged
    llm_confidence DOUBLE PRECISION,
    human_verdict BOOLEAN,  -- True = human agrees it's hallucination
    corrected_response TEXT,
    domain TEXT DEFAULT 'general',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    used_for_retraining BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_hallucination_corrections_verdict 
    ON hallucination_corrections(llm_verdict, human_verdict);
CREATE INDEX IF NOT EXISTS idx_hallucination_corrections_domain 
    ON hallucination_corrections(domain);
CREATE INDEX IF NOT EXISTS idx_hallucination_corrections_retraining 
    ON hallucination_corrections(used_for_retraining) WHERE used_for_retraining = FALSE;

-- ============================================================
-- 4. Semantic Cache Stats
-- ============================================================
CREATE TABLE IF NOT EXISTS semantic_cache_stats (
    id SERIAL PRIMARY KEY,
    model_id TEXT NOT NULL,
    cache_hits BIGINT NOT NULL DEFAULT 0,
    cache_misses BIGINT NOT NULL DEFAULT 0,
    cost_saved DOUBLE PRECISION NOT NULL DEFAULT 0,
    latency_saved_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_stats_unique 
    ON semantic_cache_stats(model_id, date);

-- ============================================================
-- 5. Agent Permissions (Cached from OPA)
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_permissions (
    id SERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL UNIQUE,
    allowed_tools JSONB NOT NULL DEFAULT '[]',
    rate_limits JSONB NOT NULL DEFAULT '{}',
    budget_limit DOUBLE PRECISION NOT NULL DEFAULT 100,
    allowed_models JSONB,  -- NULL means all models
    require_human_approval JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 6. Agent Activity Log
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_activity_log (
    id BIGSERIAL PRIMARY KEY,
    agent_id UUID,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'tool_call', 'policy_check', 'kill_switch', 'recovery'
    tool_name TEXT,
    tool_input JSONB,
    tool_output JSONB,
    allowed BOOLEAN NOT NULL DEFAULT TRUE,
    policy_violation TEXT,
    latency_ms DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_activity_agent ON agent_activity_log(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_activity_action ON agent_activity_log(action);
CREATE INDEX IF NOT EXISTS idx_agent_activity_created ON agent_activity_log(created_at);

-- ============================================================
-- 7. Add audit_hash to existing audit_logs table
-- ============================================================
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS audit_hash TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS signature TEXT;

-- ============================================================
-- 8. Add domain column to existing guardrail_results table
-- ============================================================
ALTER TABLE guardrail_results ADD COLUMN IF NOT EXISTS domain TEXT DEFAULT 'general';
ALTER TABLE guardrail_results ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION;
ALTER TABLE guardrail_results ADD COLUMN IF NOT EXISTS human_verified BOOLEAN DEFAULT FALSE;
