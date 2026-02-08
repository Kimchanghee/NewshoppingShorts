-- Migration: Add online status columns
-- Date: 2025-01-31

-- Add online status columns to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_online BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP NULL;

-- Verify columns were added
-- DESCRIBE users;
