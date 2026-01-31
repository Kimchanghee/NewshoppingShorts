-- Performance Optimization: Add Database Indexes
-- Created: 2026-02-01
-- Purpose: Improve query performance for authentication and admin operations

-- User table indexes
CREATE INDEX IF NOT EXISTS idx_users_subscription_expires
    ON users(subscription_expires_at)
    WHERE subscription_expires_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_active_online
    ON users(is_active, is_online)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_users_type_active
    ON users(user_type, is_active);

-- Login attempts table indexes (improve rate limiting queries)
CREATE INDEX IF NOT EXISTS idx_login_attempts_username_time
    ON login_attempts(username, attempted_at DESC);

CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_time
    ON login_attempts(ip_address, attempted_at DESC);

CREATE INDEX IF NOT EXISTS idx_login_attempts_success_time
    ON login_attempts(success, attempted_at DESC);

-- Session table indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_active_expires
    ON sessions(user_id, is_active, expires_at)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_sessions_token_active
    ON sessions(token_jti, is_active)
    WHERE is_active = TRUE;

-- Registration requests indexes
CREATE INDEX IF NOT EXISTS idx_registration_status_created
    ON registration_requests(status, created_at DESC);

-- Cleanup old data (run periodically via cron)
-- DELETE FROM login_attempts WHERE attempted_at < NOW() - INTERVAL '7 days';
-- DELETE FROM sessions WHERE is_active = FALSE AND expires_at < NOW() - INTERVAL '30 days';
