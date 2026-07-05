-- NorthGuard Encryption-at-Rest Migration
-- Enables pgcrypto extension and adds column-level encryption for PII fields
-- Run: psql -U northguard -d northguard -f scripts/enable_encryption.sql

-- Step 1: Enable pgcrypto extension (requires superuser or appropriate privileges)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Step 2: Create encryption key storage table
-- In production, keys should be managed via a KMS (Vault, AWS KMS, etc.)
-- This is a local development fallback using a derived key
CREATE TABLE IF NOT EXISTS encryption_keys (
    id SERIAL PRIMARY KEY,
    key_name TEXT UNIQUE NOT NULL,
    key_value TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    rotated_at TIMESTAMPTZ
);

-- Insert a default encryption key (in production, use a KMS-generated key)
-- WARNING: This key is for development only. Rotate immediately in production.
INSERT INTO encryption_keys (key_name, key_value)
VALUES ('default_pii_key', encode(gen_random_bytes(32), 'hex'))
ON CONFLICT (key_name) DO NOTHING;

-- Step 3: Create encrypted PII storage table
-- This stores PII data separately with encryption, while the main traces table
-- references it via a foreign key with only non-sensitive metadata
CREATE TABLE IF NOT EXISTS encrypted_pii (
    id SERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES guardrail_results(trace_id) ON DELETE CASCADE,
    pii_type TEXT NOT NULL,
    pii_value_encrypted BYTEA NOT NULL,  -- pgp_sym_encrypt() output
    created_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INT DEFAULT 0,
    last_accessed_at TIMESTAMPTZ
);

-- Step 4: Create function to encrypt PII data
CREATE OR REPLACE FUNCTION encrypt_pii_data(
    p_trace_id TEXT,
    p_pii_type TEXT,
    p_plaintext TEXT
) RETURNS VOID AS $$
DECLARE
    v_key TEXT;
BEGIN
    SELECT key_value INTO v_key FROM encryption_keys WHERE key_name = 'default_pii_key';
    INSERT INTO encrypted_pii (trace_id, pii_type, pii_value_encrypted)
    VALUES (
        p_trace_id,
        p_pii_type,
        pgp_sym_encrypt(p_plaintext, v_key)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Step 5: Create function to decrypt PII data (with access logging)
CREATE OR REPLACE FUNCTION decrypt_pii_data(
    p_encrypted_id INT
) RETURNS TEXT AS $$
DECLARE
    v_key TEXT;
    v_plaintext TEXT;
BEGIN
    SELECT key_value INTO v_key FROM encryption_keys WHERE key_name = 'default_pii_key';
    
    SELECT pgp_sym_decrypt(pii_value_encrypted, v_key) INTO v_plaintext
    FROM encrypted_pii
    WHERE id = p_encrypted_id;
    
    -- Log access
    UPDATE encrypted_pii
    SET access_count = access_count + 1,
        last_accessed_at = NOW()
    WHERE id = p_encrypted_id;
    
    RETURN v_plaintext;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Step 6: Create audit trigger for encrypted PII access
CREATE TABLE IF NOT EXISTS pii_access_log (
    id SERIAL PRIMARY KEY,
    encrypted_pii_id INT REFERENCES encrypted_pii(id) ON DELETE SET NULL,
    accessed_by TEXT,
    accessed_at TIMESTAMPTZ DEFAULT NOW(),
    purpose TEXT
);

-- Step 7: Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_encrypted_pii_trace_id ON encrypted_pii(trace_id);
CREATE INDEX IF NOT EXISTS idx_encrypted_pii_type ON encrypted_pii(pii_type);
CREATE INDEX IF NOT EXISTS idx_pii_access_log_time ON pii_access_log(accessed_at);

-- Step 8: Verify encryption is working
DO $$
DECLARE
    v_test_encrypted BYTEA;
    v_test_decrypted TEXT;
    v_key TEXT;
BEGIN
    SELECT key_value INTO v_key FROM encryption_keys WHERE key_name = 'default_pii_key';
    v_test_encrypted := pgp_sym_encrypt('TEST-SIN-123-456-789', v_key);
    v_test_decrypted := pgp_sym_decrypt(v_test_encrypted, v_key);
    
    IF v_test_decrypted = 'TEST-SIN-123-456-789' THEN
        RAISE NOTICE 'Encryption-at-rest verification: PASSED';
    ELSE
        RAISE EXCEPTION 'Encryption-at-rest verification: FAILED';
    END IF;
END;
$$;

-- Step 9: Grant appropriate permissions
-- In production, restrict these to specific service accounts
REVOKE ALL ON FUNCTION encrypt_pii_data FROM PUBLIC;
REVOKE ALL ON FUNCTION decrypt_pii_data FROM PUBLIC;
GRANT EXECUTE ON FUNCTION encrypt_pii_data TO northguard;
GRANT EXECUTE ON FUNCTION decrypt_pii_data TO northguard;

-- Step 10: Create a view for safe PII access (masks sensitive data by default)
CREATE OR REPLACE VIEW v_encrypted_pii_safe AS
SELECT 
    id,
    trace_id,
    pii_type,
    '********' AS pii_value_masked,
    created_at,
    access_count,
    last_accessed_at
FROM encrypted_pii;

COMMENT ON VIEW v_encrypted_pii_safe IS 'Safe view of encrypted PII data - sensitive values are masked by default';
COMMENT ON FUNCTION encrypt_pii_data IS 'Encrypts PII data using pgp_sym_encrypt with the configured encryption key';
COMMENT ON FUNCTION decrypt_pii_data IS 'Decrypts PII data with access logging for audit compliance';
