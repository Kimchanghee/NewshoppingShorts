-- Migration: Add admin features columns to users and registration_requests tables
-- 관리자 기능용 컬럼 추가 (비밀번호 보기, 온라인 상태)
-- Date: 2025-01-31

-- Add password_plain column to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_plain VARCHAR(255) NULL;

-- Add online status columns to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_online BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP NULL;

-- Add password_plain column to registration_requests
ALTER TABLE registration_requests ADD COLUMN IF NOT EXISTS password_plain VARCHAR(255) NULL;

-- Verify columns were added
-- DESCRIBE users;
-- DESCRIBE registration_requests;
