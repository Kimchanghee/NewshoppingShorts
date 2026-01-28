-- Migration: Add work_count and work_used columns to users table
-- 사용자 테이블에 work_count, work_used 컬럼 추가
-- Date: 2025-01-29

-- Run this SQL command on your Cloud SQL instance:
-- Cloud SQL 인스턴스에서 이 SQL 명령을 실행하세요:

-- Add work_count column (작업 횟수 제한, -1 = 무제한)
ALTER TABLE users ADD COLUMN IF NOT EXISTS work_count INT NOT NULL DEFAULT -1;

-- Add work_used column (사용한 작업 횟수)
ALTER TABLE users ADD COLUMN IF NOT EXISTS work_used INT NOT NULL DEFAULT 0;

-- If using MySQL version that doesn't support IF NOT EXISTS, use:
-- MySQL 버전이 IF NOT EXISTS를 지원하지 않는 경우:
-- ALTER TABLE users ADD COLUMN work_count INT NOT NULL DEFAULT -1;
-- ALTER TABLE users ADD COLUMN work_used INT NOT NULL DEFAULT 0;

-- Verify columns were added
-- 컬럼 추가 확인
-- DESCRIBE users;
