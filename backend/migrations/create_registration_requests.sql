-- Migration: Create registration_requests table
-- 회원가입 요청 테이블 생성
--
-- Run this SQL on your Cloud SQL instance:
-- gcloud sql connect ssmaker-auth --user=root --project=project-d0118f2c-58f4-4081-864

USE ssmaker_auth;

-- Create registration_requests table if not exists
CREATE TABLE IF NOT EXISTS registration_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '가입자 명',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '요청 아이디',
    password_hash VARCHAR(255) NOT NULL COMMENT '해시된 비밀번호',
    contact VARCHAR(50) NOT NULL COMMENT '연락처',
    status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending' COMMENT '상태',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '생성 일시',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 일시',
    reviewed_at TIMESTAMP NULL COMMENT '검토 일시',
    reviewed_by INT NULL COMMENT '검토한 관리자 ID',
    rejection_reason TEXT NULL COMMENT '거부 사유',
    INDEX idx_status (status),
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='회원가입 요청 테이블';

-- Verify table created
SHOW TABLES LIKE 'registration_requests';
SELECT COUNT(*) as total FROM registration_requests;
