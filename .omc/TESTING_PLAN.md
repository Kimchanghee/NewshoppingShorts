# Security Fixes Testing Plan

## Pre-Deployment Testing

### 1. Database Migration Testing

```bash
# Test migrations on a copy of production database
psql -U user -d test_db -f backend/migrations/remove_password_plain.sql
psql -U user -d test_db -f backend/migrations/add_performance_indexes.sql

# Verify migrations
psql -U user -d test_db -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'password_plain';"
# Should return 0 rows

psql -U user -d test_db -c "SELECT indexname FROM pg_indexes WHERE tablename IN ('users', 'login_attempts', 'sessions');"
# Should show all new indexes
```

### 2. Security Testing

#### A. Username Enumeration Test
```python
import requests

# Test that valid and invalid usernames return the same error
resp1 = requests.post("https://api/user/login/god", json={
    "id": "validuser",
    "pw": "wrongpassword",
    "key": "ssmaker",
    "ip": "1.2.3.4"
})

resp2 = requests.post("https://api/user/login/god", json={
    "id": "invaliduser999",
    "pw": "wrongpassword",
    "key": "ssmaker",
    "ip": "1.2.3.4"
})

assert resp1.json()["status"] == resp2.json()["status"] == "EU001"
print("✅ Username enumeration prevented")
```

#### B. Rate Limiting Test
```python
# Test X-Forwarded-For spoofing prevention
for i in range(20):
    requests.post("https://api/user/login/god",
                  headers={"X-Forwarded-For": f"1.2.3.{i}"},
                  json={"id": "test", "pw": "test", "key": "ssmaker", "ip": "1.2.3.4"})

# Should be rate limited after 10 attempts despite different X-Forwarded-For
print("✅ Rate limiting works correctly")
```

#### C. JWT Blacklist Test
```python
# Login
login_resp = requests.post("https://api/user/login/god", json={
    "id": "testuser",
    "pw": "testpass",
    "key": "ssmaker",
    "ip": "1.2.3.4"
})
token = login_resp.json()["data"]["token"]

# Logout
requests.post("https://api/user/logout", json={
    "user_id": "1",
    "token": token
})

# Try to use token after logout (should fail)
resp = requests.post("https://api/user/check-session", json={
    "user_id": "1",
    "token": token,
    "ip": "1.2.3.4"
})
assert resp.json()["status"] == "EU003"
print("✅ JWT blacklist working")
```

#### D. Session Fixation Test
```python
# Login twice with same user
resp1 = login_user("testuser", "testpass")
token1 = resp1["data"]["token"]
jti1 = decode_jwt(token1)["jti"]

resp2 = login_user("testuser", "testpass")
token2 = resp2["data"]["token"]
jti2 = decode_jwt(token2)["jti"]

assert jti1 != jti2
print("✅ New JTI generated on each login")
```

### 3. Functionality Testing

#### A. Registration with Race Condition Test
```python
import threading
import requests

results = []

def register_user(username):
    try:
        resp = requests.post("https://api/user/register/request", json={
            "name": "Test User",
            "username": username,
            "password": "TestPass123",
            "contact": "01012345678"
        })
        results.append(resp.json())
    except Exception as e:
        results.append({"error": str(e)})

# Try to register same username simultaneously
threads = [threading.Thread(target=register_user, args=("racetest",)) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

success_count = sum(1 for r in results if r.get("success") == True)
assert success_count == 1
print("✅ Race condition prevented - only one registration succeeded")
```

#### B. Force Logout Transaction Test
```python
# Login
login1 = login_user("testuser", "testpass")
session1_token = login1["data"]["token"]

# Simulate network interruption during force login
# This should either: both sessions valid OR only new session valid
# Never: both sessions invalid
try:
    login2 = login_user("testuser", "testpass", force=True)
    # Verify old session is invalid
    check1 = check_session(session1_token)
    assert check1["status"] == "EU003"

    # Verify new session is valid
    check2 = check_session(login2["data"]["token"])
    assert check2["status"] == True
    print("✅ Force logout transaction atomicity verified")
except:
    # Rollback should have occurred
    check1 = check_session(session1_token)
    assert check1["status"] == True
    print("✅ Rollback successful - old session still valid")
```

#### C. Password Validation Test
```python
# Test server-side password validation
test_cases = [
    ("abc", False, "Too short"),
    ("abcdef", False, "No number"),
    ("123456", False, "No letter"),
    ("abc123", True, "Valid"),
    ("TestPass123", True, "Valid strong"),
]

for password, should_succeed, desc in test_cases:
    resp = requests.post("https://api/user/register/request", json={
        "name": "Test",
        "username": f"test_{password}",
        "password": password,
        "contact": "01012345678"
    })

    if should_succeed:
        assert resp.json()["success"] == True, f"Failed: {desc}"
    else:
        assert resp.json()["success"] == False, f"Failed: {desc}"

print("✅ Password validation working")
```

### 4. Performance Testing

#### A. Index Performance Test
```sql
-- Before indexes
EXPLAIN ANALYZE
SELECT * FROM users
WHERE is_active = TRUE AND is_online = TRUE;

-- Should use idx_users_active_online
-- Check execution time < 10ms for 10K users

EXPLAIN ANALYZE
SELECT * FROM login_attempts
WHERE username = 'testuser'
  AND attempted_at > NOW() - INTERVAL '15 minutes'
  AND success = FALSE;

-- Should use idx_login_attempts_username_time
-- Check execution time < 5ms
```

#### B. Connection Pool Test
```python
import concurrent.futures
import time

def make_request():
    start = time.time()
    requests.get("https://api/user/admin/users")
    return time.time() - start

# Test 100 concurrent requests
with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
    futures = [executor.submit(make_request) for _ in range(100)]
    times = [f.result() for f in futures]

avg_time = sum(times) / len(times)
assert avg_time < 1.0  # Should average under 1 second
print(f"✅ Connection pool optimized - avg response: {avg_time:.2f}s")
```

### 5. UI Testing

#### A. Worker Thread Management
```python
# Rapid username checks should not crash
for i in range(10):
    check_username(f"user{i}")
    time.sleep(0.1)  # Simulate rapid clicking

# Last check should complete successfully
assert last_check_result != None
print("✅ Worker threads managed correctly")
```

#### B. Online Status Display
```python
# Login user
login_user("testuser", "testpass")

# Wait 2 seconds
time.sleep(2)

# Check admin dashboard shows user as online
dashboard_data = get_admin_dashboard_data()
user = next(u for u in dashboard_data["users"] if u["username"] == "testuser")
assert user["is_online"] == True
print("✅ Online status correct")
```

### 6. Timezone Testing
```python
from datetime import datetime, timezone

# Create user with subscription
user = create_user_with_subscription(days=30)

# Get expiry in different timezones
server_expiry = user["subscription_expires_at"]  # Should be UTC
admin_display = get_admin_dashboard_user(user["id"])["expires_display"]  # Should be KST

# Verify both represent same moment
server_dt = datetime.fromisoformat(server_expiry).replace(tzinfo=timezone.utc)
admin_dt = datetime.fromisoformat(admin_display).replace(tzinfo=timezone.utc)
assert abs((server_dt - admin_dt).total_seconds()) < 1
print("✅ Timezone handling correct")
```

## Post-Deployment Monitoring

### 1. Monitor Logs
```bash
# Check for errors in first 24 hours
tail -f logs/app.log | grep -i "error\|exception\|critical"
```

### 2. Monitor Performance
- Average response time < 500ms
- Rate limit triggers < 10/hour
- Failed login rate < 5%

### 3. Database Monitoring
```sql
-- Check session table growth
SELECT COUNT(*), MAX(created_at)
FROM sessions
WHERE created_at > NOW() - INTERVAL '24 hours';

-- Check login attempts cleanup
SELECT COUNT(*)
FROM login_attempts
WHERE attempted_at < NOW() - INTERVAL '7 days';
-- Should be 0 after cron runs
```

## Rollback Plan

If critical issues found:

1. **Revert code changes**: `git revert <commit-hash>`
2. **Rollback database** (if needed):
   ```sql
   -- Note: password_plain migration is NOT reversible
   -- Index migration is reversible:
   DROP INDEX idx_users_subscription_expires;
   -- ... (drop all other indexes)
   ```
3. **Restart services**: `systemctl restart ssmaker-api`
4. **Verify rollback**: Run basic login/registration test

## Success Criteria

✅ All security tests pass
✅ All functionality tests pass
✅ Performance tests show improvement
✅ No errors in logs for 24 hours
✅ User reports no issues
