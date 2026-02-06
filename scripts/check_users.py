# -*- coding: utf-8 -*-
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_SERVER_URL", "https://ssmaker-auth-api-1049571775048.us-central1.run.app")
API_KEY = os.getenv("SSMAKER_ADMIN_KEY") or os.getenv("ADMIN_API_KEY")

headers = {"X-Admin-API-Key": API_KEY, "Content-Type": "application/json"}

# Get all users
all_users = []
page = 1

while True:
    url = f"{API_URL}/user/admin/users?page={page}&page_size=100"
    resp = requests.get(url, headers=headers, timeout=30)
    
    if resp.status_code != 200:
        break
    
    data = resp.json()
    users = data.get("users", [])
    total = data.get("total", 0)
    
    if not users:
        break
    
    all_users.extend(users)
    
    if len(all_users) >= total:
        break
    
    page += 1

# Calculate daily stats
daily_stats = {}
for user in all_users:
    created_at = user.get("created_at", "")
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            dt_kst = dt + timedelta(hours=9)
            date_str = dt_kst.strftime("%Y-%m-%d")
            daily_stats[date_str] = daily_stats.get(date_str, 0) + 1
        except:
            pass

# Write to file
with open("user_report.txt", "w", encoding="utf-8") as f:
    f.write("=" * 50 + "\n")
    f.write(f"TOTAL USERS IN DATABASE: {len(all_users)}\n")
    f.write("=" * 50 + "\n\n")
    
    f.write("DAILY REGISTRATION STATS (KST):\n")
    for date in sorted(daily_stats.keys(), reverse=True):
        today_marker = " <-- TODAY" if date == datetime.now().strftime("%Y-%m-%d") else ""
        f.write(f"  {date}: {daily_stats[date]} users{today_marker}\n")
    
    today_count = daily_stats.get(datetime.now().strftime("%Y-%m-%d"), 0)
    f.write(f"\n*** TODAY ({datetime.now().strftime('%Y-%m-%d')}): {today_count} NEW USERS ***\n\n")
    
    f.write("ALL USERS:\n")
    f.write("-" * 100 + "\n")
    
    all_users_sorted = sorted(all_users, key=lambda x: x.get("created_at", ""), reverse=True)
    
    for user in all_users_sorted:
        user_id = user.get("id", "")
        username = user.get("username", "-")
        name = user.get("name") or "-"
        phone = user.get("phone") or "-"
        user_type = user.get("user_type", "-")
        
        created_at = user.get("created_at", "")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                dt_kst = dt + timedelta(hours=9)
                created_str = dt_kst.strftime("%Y-%m-%d %H:%M:%S")
            except:
                created_str = created_at
        else:
            created_str = "-"
        
        f.write(f"ID:{user_id} | {username} | {name} | {phone} | {created_str} | {user_type}\n")
    
    f.write("-" * 100 + "\n")

print(f"Report saved to user_report.txt")
print(f"Total users: {len(all_users)}")
