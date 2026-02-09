-- Migration: Add payment error tracking and user payment stats tables
-- Created: 2026-02-09
-- Description: 결제 오류 로그 및 사용자 결제 통계 테이블 추가

-- Payment Error Logs table (결제 오류 로그)
CREATE TABLE IF NOT EXISTS payment_error_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    error_type VARCHAR(50) NOT NULL,
    error_code VARCHAR(50),
    error_message VARCHAR(500),
    endpoint VARCHAR(100),
    payment_id VARCHAR(64),
    plan_id VARCHAR(50),
    context VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for payment_error_logs
CREATE INDEX IF NOT EXISTS ix_payment_error_logs_user_id ON payment_error_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_payment_error_logs_created_at ON payment_error_logs(created_at);
CREATE INDEX IF NOT EXISTS ix_payment_error_logs_error_type ON payment_error_logs(error_type);
CREATE INDEX IF NOT EXISTS ix_payment_error_logs_user_created ON payment_error_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_payment_error_logs_payment_id ON payment_error_logs(payment_id);

-- User Payment Stats table (사용자 결제 통계)
CREATE TABLE IF NOT EXISTS user_payment_stats (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL UNIQUE,
    consecutive_fail_count INTEGER DEFAULT 0 NOT NULL,
    total_fail_count INTEGER DEFAULT 0 NOT NULL,
    total_success_count INTEGER DEFAULT 0 NOT NULL,
    last_fail_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for user_payment_stats
CREATE INDEX IF NOT EXISTS ix_user_payment_stats_user_id ON user_payment_stats(user_id);

-- Comment: These tables support the following features:
-- 1. Payment error logging and monitoring
-- 2. User-level payment failure tracking (consecutive fails)
-- 3. Admin dashboard for payment health monitoring
-- 4. Rate limiting based on payment failure patterns
