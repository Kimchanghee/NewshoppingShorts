-- Migration: Add login_count column to users table
-- 사용자 테이블에 login_count 컬럼 추가

-- Run this SQL command on your Cloud SQL instance:
-- Cloud SQL 인스턴스에서 이 SQL 명령을 실행하세요:

-- Check if column exists and add if not
-- 컬럼이 존재하지 않으면 추가

ALTER TABLE users ADD COLUMN IF NOT EXISTS login_count INT NOT NULL DEFAULT 0;

-- If using MySQL version that doesn't support IF NOT EXISTS, use:
-- MySQL 버전이 IF NOT EXISTS를 지원하지 않는 경우:
-- ALTER TABLE users ADD COLUMN login_count INT NOT NULL DEFAULT 0;

-- Update existing users to have 0 login count (if needed)
-- 기존 사용자의 login_count를 0으로 설정 (필요한 경우)
-- UPDATE users SET login_count = 0 WHERE login_count IS NULL;
