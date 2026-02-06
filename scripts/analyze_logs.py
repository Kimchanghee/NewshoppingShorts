# -*- coding: utf-8 -*-
"""
Cloud Run 로그 분석 - 회원가입 시도 확인
"""
import json
from datetime import datetime, timedelta
from collections import defaultdict

# Load logs
with open("cloud_logs.json", "r", encoding="utf-8") as f:
    logs = json.load(f)

print(f"Total log entries: {len(logs)}")
print("=" * 80)

# Analyze logs
register_attempts = []
register_success = []
register_fail = []
http_requests = defaultdict(int)
error_logs = []

for entry in logs:
    text = entry.get("textPayload", "")
    timestamp = entry.get("timestamp", "")
    
    # Check for registration attempts
    if "Register" in text or "register" in text or "/register" in text.lower():
        register_attempts.append({
            "time": timestamp,
            "text": text[:200]
        })
        
        if "Success" in text:
            register_success.append({"time": timestamp, "text": text[:200]})
        elif "Fail" in text or "error" in text.lower():
            register_fail.append({"time": timestamp, "text": text[:200]})
    
    # Check HTTP requests
    http_request = entry.get("httpRequest", {})
    if http_request:
        path = http_request.get("requestUrl", "")
        method = http_request.get("requestMethod", "")
        status = http_request.get("status", 0)
        if "/register" in path or "/user" in path:
            http_requests[f"{method} {path} -> {status}"] += 1
    
    # Check for errors
    severity = entry.get("severity", "")
    if severity in ("ERROR", "CRITICAL"):
        error_logs.append({
            "time": timestamp,
            "severity": severity,
            "text": text[:300]
        })

# Output results
print("\n=== REGISTRATION ATTEMPTS (last 24h) ===")
for item in register_attempts[:30]:
    print(f"  {item['time']}: {item['text']}")

print(f"\n=== REGISTRATION SUCCESS: {len(register_success)} ===")
for item in register_success[:20]:
    print(f"  {item['time']}: {item['text']}")

print(f"\n=== REGISTRATION FAILS: {len(register_fail)} ===")
for item in register_fail[:20]:
    print(f"  {item['time']}: {item['text']}")

print(f"\n=== HTTP REQUESTS TO /register or /user ===")
for path, count in sorted(http_requests.items(), key=lambda x: -x[1])[:20]:
    print(f"  {count:4d} | {path}")

print(f"\n=== ERROR LOGS: {len(error_logs)} ===")
for item in error_logs[:10]:
    print(f"  {item['time']} [{item['severity']}]: {item['text']}")

print("\n" + "=" * 80)
print("Analysis complete")
