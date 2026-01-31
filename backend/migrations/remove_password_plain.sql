-- Remove password_plain columns (CRITICAL SECURITY FIX)
-- These columns stored plaintext passwords which is a severe security vulnerability

ALTER TABLE users DROP COLUMN IF EXISTS password_plain;
ALTER TABLE registration_requests DROP COLUMN IF EXISTS password_plain;
