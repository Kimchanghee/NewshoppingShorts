# -*- coding: utf-8 -*-
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_SERVER_URL", "https://ssmaker-auth-api-1049571775048.us-central1.run.app")
API_KEY = os.getenv("SSMAKER_ADMIN_KEY") or os.getenv("ADMIN_API_KEY")

headers = {"X-Admin-API-Key": API_KEY, "Content-Type": "application/json"}

with open("registration_report.txt", "w", encoding="utf-8") as f:
    f.write("=" * 60 + "\n")
    f.write("CHECKING REGISTRATION REQUESTS AND LOGIN ATTEMPTS\n")
    f.write("=" * 60 + "\n\n")

    # 1. 구독 요청 확인
    f.write("1. SUBSCRIPTION REQUESTS:\n")
    resp = requests.get(f"{API_URL}/user/subscription/requests", headers=headers, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        requests_list = data.get("requests", [])
        f.write(f"   Total requests: {len(requests_list)}\n")
        for req in requests_list:
            req_id = req.get("id")
            user_id = req.get("user_id")
            username = req.get("username")
            status = req.get("status")
            message = req.get("message", "")
            created = req.get("created_at", "")
            f.write(f"   ID:{req_id} | User:{user_id} | {username} | {status} | {created} | {message}\n")
    else:
        f.write(f"   Error: {resp.status_code}\n")

    # 2. 통계 확인
    f.write("\n2. SUBSCRIPTION STATS:\n")
    resp = requests.get(f"{API_URL}/user/subscription/stats", headers=headers, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        f.write(f"   Pending: {data.get('pending', 0)}\n")
        f.write(f"   Approved: {data.get('approved', 0)}\n")
        f.write(f"   Rejected: {data.get('rejected', 0)}\n")
    else:
        f.write(f"   Error: {resp.status_code}\n")

    # 3. Admin 통계 확인
    f.write("\n3. ADMIN STATS:\n")
    resp = requests.get(f"{API_URL}/user/admin/stats", headers=headers, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        f.write(f"   Users: {data.get('users', {})}\n")
        f.write(f"   Registration Requests: {data.get('registration_requests', {})}\n")
    else:
        f.write(f"   Error: {resp.status_code}\n")

    f.write("\n" + "=" * 60 + "\n")

print("Report saved to registration_report.txt")
