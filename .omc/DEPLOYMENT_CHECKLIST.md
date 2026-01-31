# Deployment Checklist for Security Fixes

## Pre-Deployment (Development Environment)

### 1. Code Review
- [ ] All code changes reviewed and committed
- [ ] No merge conflicts
- [ ] No syntax errors (`python -m py_compile backend/**/*.py`)
- [ ] Type hints validated (`mypy backend/` if using mypy)

### 2. Local Testing
- [ ] All unit tests pass
- [ ] Security tests pass (see TESTING_PLAN.md)
- [ ] Integration tests pass
- [ ] Manual smoke test completed

### 3. Environment Configuration
- [ ] `.env` file created from `.env.example`
- [ ] `ADMIN_API_KEY` generated with secure random string
- [ ] `JWT_SECRET_KEY` generated with secure random string
- [ ] Database credentials configured
- [ ] All environment variables validated

### 4. Database Preparation
- [ ] Database backup created
- [ ] Migration SQL files reviewed
- [ ] Test migration on copy of production database
- [ ] Migration rollback plan documented

## Deployment Steps

### Step 1: Backup (CRITICAL)
```bash
# Database backup
pg_dump -U user dbname > backup_$(date +%Y%m%d_%H%M%S).sql

# Code backup
git tag pre-security-fixes-$(date +%Y%m%d)
git push origin pre-security-fixes-$(date +%Y%m%d)
```

- [ ] Database backup created and verified
- [ ] Git tag created
- [ ] Backup stored in safe location

### Step 2: Database Migration
```bash
# Connect to production database
psql -U user -d production_db

# Run migrations
\i backend/migrations/remove_password_plain.sql
\i backend/migrations/add_performance_indexes.sql

# Verify
SELECT column_name FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'password_plain';
-- Should return 0 rows

SELECT indexname FROM pg_indexes
WHERE tablename IN ('users', 'login_attempts', 'sessions');
-- Should show all new indexes
```

- [ ] password_plain columns removed
- [ ] Performance indexes created
- [ ] Migration verification successful

### Step 3: Code Deployment
```bash
# Pull latest code
git pull origin main

# Install dependencies (if any new ones)
pip install -r requirements.txt

# Set environment variables
export ADMIN_API_KEY="your-secure-key"
export JWT_SECRET_KEY="your-secure-key"
# ... (all other env vars)

# Or use .env file
cp .env.example .env
# Edit .env with production values
```

- [ ] Code pulled from repository
- [ ] Dependencies installed
- [ ] Environment variables configured
- [ ] `.env` file secured (chmod 600)

### Step 4: Service Restart
```bash
# Restart backend API
systemctl restart ssmaker-api
# or
docker-compose restart api

# Check logs for errors
tail -f logs/app.log
journalctl -u ssmaker-api -f
```

- [ ] Service restarted successfully
- [ ] No errors in startup logs
- [ ] Health check endpoint responding

### Step 5: Smoke Testing
```bash
# Test login
curl -X POST https://api/user/login/god \
  -H "Content-Type: application/json" \
  -d '{"id":"testuser","pw":"testpass","key":"ssmaker","ip":"1.2.3.4"}'

# Test registration
curl -X POST https://api/user/register/request \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","username":"newuser","password":"Test123","contact":"01012345678"}'

# Test admin endpoint
curl https://api/user/admin/users \
  -H "X-Admin-API-Key: your-admin-key"
```

- [ ] Login works
- [ ] Registration works
- [ ] Admin dashboard accessible
- [ ] No errors in logs

## Post-Deployment Verification

### Immediate (First Hour)
- [ ] Monitor error logs continuously
- [ ] Check response times (< 500ms average)
- [ ] Verify rate limiting working (test with 10 rapid requests)
- [ ] Test username enumeration prevention
- [ ] Test JWT blacklist (logout + reuse token)

### Short-term (First 24 Hours)
- [ ] Monitor user login success rate (> 95%)
- [ ] Check database performance (query times)
- [ ] Verify no session leaks (old sessions cleaned up)
- [ ] Monitor memory usage (JWT blacklist growth)
- [ ] Check for any user-reported issues

### Medium-term (First Week)
- [ ] Review security logs for anomalies
- [ ] Check database size growth (should be normal)
- [ ] Verify performance improvements from indexes
- [ ] Monitor rate limiting trigger frequency
- [ ] Review user feedback

## Rollback Procedure

### If Critical Issues Found:

1. **Immediate Rollback (< 5 minutes)**
```bash
# Revert to previous code
git checkout pre-security-fixes-YYYYMMDD
systemctl restart ssmaker-api

# Database indexes can stay (they're harmless)
# password_plain removal is NOT reversible!
```

2. **Notify Team**
- [ ] Notify developers of rollback
- [ ] Document issues found
- [ ] Create incident report

3. **Post-Rollback**
- [ ] Investigate root cause
- [ ] Fix issues in development
- [ ] Re-test thoroughly
- [ ] Schedule new deployment

## Success Criteria

### Required (Must Pass All)
- ✅ Zero critical errors in logs
- ✅ User login success rate > 95%
- ✅ Admin dashboard functional
- ✅ Response times < 500ms
- ✅ Security tests pass

### Desired (Nice to Have)
- ✅ Performance improvement visible
- ✅ Rate limiting triggers < 5/hour
- ✅ Zero user complaints
- ✅ Database query times improved

## Security Validation

### Post-Deployment Security Checks
```bash
# 1. Verify password_plain is gone
psql -c "SELECT password_plain FROM users LIMIT 1;"
# Should ERROR: column "password_plain" does not exist

# 2. Test username enumeration
# Both should return same error code
curl ... -d '{"id":"validuser","pw":"wrong",...}'
curl ... -d '{"id":"invaliduser","pw":"wrong",...}'

# 3. Test rate limiting
for i in {1..15}; do
  curl ... -d '{"id":"test","pw":"test",...}'
done
# Should get rate limited after attempt 10

# 4. Test JWT blacklist
TOKEN=$(curl ... | jq -r '.data.token')
curl ... -d '{"user_id":"1","token":"'$TOKEN'",...}'  # logout
curl ... -d '{"user_id":"1","token":"'$TOKEN'",...}'  # check
# Should return EU003 (session invalid)
```

- [ ] password_plain verified removed
- [ ] Username enumeration prevented
- [ ] Rate limiting working
- [ ] JWT blacklist working

## Final Sign-off

- [ ] Technical Lead Approval: ________________ Date: ________
- [ ] Security Review Complete: ________________ Date: ________
- [ ] QA Testing Complete: ________________ Date: ________
- [ ] Deployment Successful: ________________ Date: ________

## Notes

Record any issues, observations, or deviations from this checklist:

```
[Space for notes]
```

## Contacts

- **Technical Lead**: ________________
- **Database Admin**: ________________
- **DevOps**: ________________
- **On-Call**: ________________
