# Database Migrations

This directory contains SQL migration scripts for the SSMaker authentication system database. All migrations must be applied in order to maintain database schema consistency across environments.

## Database Overview

The SSMaker Auth system uses the following tables:

| Table | Purpose |
|-------|---------|
| `users` | User accounts with authentication and subscription data |
| `registration_requests` | Pending user registration requests awaiting admin approval |
| `login_attempts` | Rate limiting and security audit trail |
| `sessions` | Active user sessions and JWT token tracking |

## Migration Files

### 1. create_registration_requests.sql

**Status:** Core schema migration
**Dependencies:** None (runs first)
**Database compatibility:** MySQL 5.7+, PostgreSQL 10+

Creates the `registration_requests` table for managing user sign-ups that require admin approval before account activation.

**Tables affected:**
- `registration_requests` (created)

**Key columns:**
- `id` - Auto-incremented primary key
- `username` - Unique identifier (must match user registration)
- `password_hash` - Bcrypt hashed password (never plaintext)
- `status` - Enum: `pending`, `approved`, `rejected`
- `reviewed_at` - Timestamp when admin reviewed request
- `reviewed_by` - Admin user ID who approved/rejected
- `rejection_reason` - Optional reason for rejection

**Indexes created:**
- `idx_status` - For filtering by approval status
- `idx_username` - For lookups by username

### 2. add_login_count.sql

**Status:** Feature migration
**Dependencies:** `users` table must exist
**Date created:** 2025-01-29

Adds login tracking to user accounts for analytics and audit purposes.

**Tables affected:**
- `users` - Adds `login_count` column

**Change:**
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS login_count INT NOT NULL DEFAULT 0;
```

**Purpose:** Track number of times user has successfully logged in. Incremented by auth service on successful login.

### 3. add_work_count.sql

**Status:** Feature migration (subscription/trial management)
**Dependencies:** `users` table must exist
**Date created:** 2025-01-29

Implements work quota system for trial and subscriber accounts.

**Tables affected:**
- `users` - Adds `work_count` and `work_used` columns

**Changes:**
```sql
-- work_count: Maximum number of jobs allowed (-1 = unlimited)
ALTER TABLE users ADD COLUMN IF NOT EXISTS work_count INT NOT NULL DEFAULT -1;

-- work_used: Number of jobs already used
ALTER TABLE users ADD COLUMN IF NOT EXISTS work_used INT NOT NULL DEFAULT 0;
```

**Usage:**
- Trial accounts: `work_count = 3` (3 free jobs)
- Subscribers: `work_count = -1` (unlimited)
- Admins: `work_count = -1` (unlimited)

### 4. add_admin_columns.sql

**Status:** Feature migration (admin dashboard)
**Dependencies:** `users` and `registration_requests` tables must exist
**Date created:** 2025-01-31

Adds columns for admin dashboard features including online status tracking and password visibility.

**Tables affected:**
- `users`
- `registration_requests`

**Changes:**
```sql
-- Online status tracking
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_online BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP NULL;

-- Password viewing (DEPRECATED - see security notes below)
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_plain VARCHAR(255) NULL;
ALTER TABLE registration_requests ADD COLUMN IF NOT EXISTS password_plain VARCHAR(255) NULL;
```

**Security Note:** The `password_plain` columns in this migration are intentionally deprecated. These columns store plaintext passwords and should be removed with the next security migration. See `remove_password_plain.sql`.

### 5. remove_password_plain.sql

**Status:** CRITICAL SECURITY MIGRATION
**Dependencies:** Must run after add_admin_columns.sql
**Safety:** NOT REVERSIBLE - Plaintext passwords are permanently deleted

Removes insecure plaintext password storage from database.

**Tables affected:**
- `users`
- `registration_requests`

**Changes:**
```sql
ALTER TABLE users DROP COLUMN IF EXISTS password_plain;
ALTER TABLE registration_requests DROP COLUMN IF EXISTS password_plain;
```

**Why this matters:**
- Plaintext passwords violate security standards (PCI-DSS, GDPR, etc.)
- If database is compromised, all user passwords are exposed
- Passwords should only be stored as irreversible hashes
- This migration permanently deletes any stored plaintext passwords

**Before running:**
1. Ensure admin dashboard no longer relies on password_plain
2. Implement password reset flow for admin-initiated resets
3. Test in staging environment first
4. Schedule during maintenance window (data is permanently deleted)

### 6. add_performance_indexes.sql

**Status:** Performance optimization
**Dependencies:** Recommended after all schema changes complete
**Date created:** 2026-02-01

Adds indexes to improve query performance for authentication, rate limiting, and admin operations.

**Indexes created:**

**User table (5 indexes):**
```
idx_users_subscription_expires - Subscription expiry checks
idx_users_active_online         - Admin dashboard active users list
idx_users_type_active           - Filter by user type (trial/subscriber/admin)
```

**Login attempts table (3 indexes):**
```
idx_login_attempts_username_time - Rate limiting: failed logins per username
idx_login_attempts_ip_time       - Rate limiting: failed logins per IP
idx_login_attempts_success_time  - Failed login analysis
```

**Sessions table (2 indexes):**
```
idx_sessions_user_active_expires - Active session lookup
idx_sessions_token_active        - Token validation (JTI)
```

**Registration requests table (1 index):**
```
idx_registration_status_created - Filter pending/approved/rejected requests
```

**Performance impact:**
- Write operations: Minimal impact (indexes updated automatically)
- Read operations: Significant improvement (5-10x faster on indexed queries)
- Storage: ~2-5MB additional disk space

## Migration Order

**Critical:** Migrations must be applied in this exact order:

```
1. create_registration_requests.sql      (Foundation)
2. add_login_count.sql                   (Feature)
3. add_work_count.sql                    (Feature)
4. add_admin_columns.sql                 (Feature)
5. remove_password_plain.sql             (SECURITY - mandatory before production)
6. add_performance_indexes.sql           (Optimization)
```

## How to Run Migrations

### Option 1: Cloud SQL (Google Cloud)

**Connect to Cloud SQL:**
```bash
gcloud sql connect ssmaker-auth --user=root --project=YOUR_PROJECT_ID
```

**Run migration:**
```sql
USE ssmaker_auth;
SOURCE /path/to/migrations/add_performance_indexes.sql;
```

Or import file from gcloud CLI:
```bash
gcloud sql import sql ssmaker-auth \
  gs://your-bucket/add_performance_indexes.sql \
  --database=ssmaker_auth
```

### Option 2: MySQL CLI

**For local MySQL:**
```bash
mysql -h your-host -u username -p database_name < migrations/add_performance_indexes.sql
```

**For remote MySQL:**
```bash
mysql -h your-host -P 3306 -u username -p database_name < migrations/add_performance_indexes.sql
```

### Option 3: PostgreSQL

**For PostgreSQL databases:**
```bash
psql -h your-host -U username -d database_name -f migrations/add_performance_indexes.sql
```

### Option 4: Python (Recommended for deployment)

Use the migration runner script:

```bash
python backend/run_migration.py --migration add_performance_indexes.sql
```

**Script features:**
- Automatic database connection
- Transaction rollback on error
- Detailed logging
- Backup creation before migration

## Verification

### Verify Migration Applied

**Check if columns exist:**
```sql
-- MySQL
DESCRIBE users;
SHOW INDEXES FROM users;

-- PostgreSQL
\d users;
SELECT indexname FROM pg_indexes WHERE tablename = 'users';
```

**Check specific columns:**
```sql
-- Verify work_count exists
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'work_count';

-- Verify password_plain is REMOVED (should return 0 rows)
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'password_plain';
```

**Check indexes:**
```sql
-- MySQL
SHOW INDEXES FROM users WHERE Key_name LIKE 'idx_%';

-- PostgreSQL
SELECT indexname, indexdef FROM pg_indexes
WHERE tablename = 'users' AND indexname LIKE 'idx_%';
```

### Health Check Query

Run this after migration to verify system health:

```sql
SELECT
    'users' as table_name,
    COUNT(*) as row_count,
    COALESCE(MAX(updated_at), NOW()) as last_updated
FROM users
UNION ALL
SELECT
    'registration_requests' as table_name,
    COUNT(*) as row_count,
    COALESCE(MAX(updated_at), NOW()) as last_updated
FROM registration_requests;
```

## Rollback Procedures

### Non-Reversible Migrations

**remove_password_plain.sql** - NOT REVERSIBLE

Once plaintext passwords are deleted, they cannot be recovered. If you need to rollback:

1. Restore database from backup taken BEFORE migration
2. Re-apply migrations starting from the backup point
3. Document reason for rollback in change management system

### Reversible Migrations (Dropping Indexes)

**For index migration only:**

```sql
-- Drop all performance indexes
DROP INDEX IF EXISTS idx_users_subscription_expires ON users;
DROP INDEX IF EXISTS idx_users_active_online ON users;
DROP INDEX IF EXISTS idx_users_type_active ON users;
DROP INDEX IF EXISTS idx_login_attempts_username_time ON login_attempts;
DROP INDEX IF EXISTS idx_login_attempts_ip_time ON login_attempts;
DROP INDEX IF EXISTS idx_login_attempts_success_time ON login_attempts;
DROP INDEX IF EXISTS idx_sessions_user_active_expires ON sessions;
DROP INDEX IF EXISTS idx_sessions_token_active ON sessions;
DROP INDEX IF EXISTS idx_registration_status_created ON registration_requests;
```

### Reversible Migrations (Dropping Columns)

**For feature columns only:**

```sql
-- Example: Remove work_count if needed
ALTER TABLE users DROP COLUMN IF EXISTS work_count;
ALTER TABLE users DROP COLUMN IF EXISTS work_used;
```

**Important:**
- Any data in dropped columns is permanently lost
- Application code must be updated to handle missing columns
- Test thoroughly in staging before production rollback

## Maintenance & Optimization

### Regular Cleanup (Recommended Weekly)

To prevent tables from growing too large, schedule these cleanup operations:

```sql
-- Clean old login attempts (older than 7 days)
DELETE FROM login_attempts
WHERE attempted_at < NOW() - INTERVAL '7 days';

-- Clean expired inactive sessions (older than 30 days)
DELETE FROM sessions
WHERE is_active = FALSE
  AND expires_at < NOW() - INTERVAL '30 days';
```

**Schedule via cron (Linux/Unix):**

```bash
# Add to crontab (runs at 2 AM daily)
0 2 * * * mysql -u username -p password -e \
  "USE ssmaker_auth; DELETE FROM login_attempts WHERE attempted_at < NOW() - INTERVAL '7 days';"
```

**Schedule via Windows Task Scheduler:**

Create batch file `cleanup.bat`:
```batch
mysql -u username -p password -e "USE ssmaker_auth; DELETE FROM login_attempts WHERE attempted_at < NOW() - INTERVAL '7 days';"
```

### Index Maintenance (Monthly)

For MySQL:
```sql
-- Optimize indexes and reclaim space
OPTIMIZE TABLE users;
OPTIMIZE TABLE registration_requests;
OPTIMIZE TABLE login_attempts;
OPTIMIZE TABLE sessions;
```

For PostgreSQL:
```sql
-- Reindex all tables
REINDEX TABLE users;
REINDEX TABLE registration_requests;
REINDEX TABLE login_attempts;
REINDEX TABLE sessions;
```

### Monitor Query Performance

Use slow query log to identify queries that need additional indexes:

**MySQL:**
```sql
-- Enable slow query log
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;

-- View slow queries
SELECT * FROM mysql.slow_log;
```

**PostgreSQL:**
```sql
-- Enable query logging
ALTER DATABASE ssmaker_auth SET log_statement = 'all';
```

## Troubleshooting

### Migration Fails: "Table already exists"

**Cause:** Migration uses `IF NOT EXISTS`, so this shouldn't occur. If it does:

```sql
-- Check if table exists
SHOW TABLES LIKE 'registration_requests';

-- If it exists, verify structure
DESCRIBE registration_requests;
```

**Solution:** Compare actual schema with migration script. If table structure differs, manually adjust before retrying.

### Migration Fails: "Column already exists"

**Cause:** Column was already added in a previous migration run.

**Solution:**
1. Verify no duplicate columns exist
2. Migrations are idempotent and safe to re-run
3. Check application logs for any related errors

### Index Creation Slow on Large Tables

**Cause:** Creating indexes locks table during creation (MySQL/PostgreSQL).

**Solution:**
```sql
-- MySQL: Use ALGORITHM=INPLACE for non-blocking index creation
ALTER TABLE users ADD INDEX idx_users_subscription_expires(subscription_expires_at), ALGORITHM=INPLACE, LOCK=NONE;
```

**Prevention:** Schedule index creation during low-traffic hours.

### Query Still Slow After Indexing

**Cause:** Index exists but query optimizer isn't using it.

**Solution:**
```sql
-- Analyze table statistics (MySQL)
ANALYZE TABLE users;

-- Force index usage
SELECT * FROM users USE INDEX (idx_users_active_online) WHERE is_active = TRUE;

-- Check query plan
EXPLAIN SELECT * FROM users WHERE is_active = TRUE AND is_online = TRUE;
```

## Safety Checklist

Before running migrations in production:

- [ ] Database backup created and tested
- [ ] Migration script reviewed by database administrator
- [ ] Staging environment migration completed and verified
- [ ] Maintenance window scheduled and communicated
- [ ] Application downtime expected and acceptable
- [ ] Rollback procedure documented and tested
- [ ] Monitoring alerts configured for post-migration verification
- [ ] DBA on-call during migration window
- [ ] Replication lag checked (if using replicated databases)

## Related Documentation

- **Database Schema:** See `/backend/app/models/` for SQLAlchemy model definitions
- **Auth Service:** See `/backend/app/services/auth_service.py` for authentication logic
- **Rate Limiting:** Implemented via `login_attempts` table (see `/backend/app/routers/auth.py`)
- **Admin Dashboard:** See `/backend/app/routers/admin.py` for admin-specific queries

## Support

For migration issues:

1. Check CloudSQL/database logs: `gcloud sql operations list --instance=ssmaker-auth`
2. Review error messages in section 1.1.1 error codes
3. Contact database administrator with:
   - Migration file name and timestamp
   - Database engine and version
   - Full error message and stack trace
   - Current table schema (DESCRIBE output)

---

**Last Updated:** 2026-02-01
**Database Version:** MySQL 5.7+ / PostgreSQL 10+
**Application Version:** SSMaker Auth API 2.0.0
