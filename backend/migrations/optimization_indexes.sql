-- Phase 6: Performance - Add database indexes SQL

-- 1. Optimize active subscription stats query
-- Used in: admin.get_stats
-- Query: SELECT count(*) FROM users WHERE is_active = true AND subscription_expires_at > now()
CREATE INDEX idx_users_active_subscription ON users (is_active, subscription_expires_at);

-- 2. Optimize rate limiting queries (username failures)
-- Used in: AuthService._check_rate_limit
-- Query: SELECT count(*) FROM login_attempts WHERE username = ? AND success = false AND attempted_at > ?
-- Note: Existing ix_login_attempts_username_time covers username+time, but success is also filtered.
CREATE INDEX idx_login_attempts_rate_limit_username ON login_attempts (username, success, attempted_at);

-- 3. Optimize rate limiting queries (IP attempts)
-- Used in: AuthService._check_rate_limit
-- Query: SELECT count(*) FROM login_attempts WHERE ip_address = ? AND attempted_at > ?
-- Note: Existing ix_login_attempts_ip_time should cover this. 
-- Just in case it's missing or consistent naming is desired:
-- CREATE INDEX idx_login_attempts_rate_limit_ip ON login_attempts (ip_address, attempted_at);
