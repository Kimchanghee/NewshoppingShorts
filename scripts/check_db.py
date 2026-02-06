# -*- coding: utf-8 -*-
"""
Database check script - 사용자 가입 현황 확인
"""
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check if we can connect to Google Cloud SQL
print("=" * 60)
print("Google Cloud SQL - 사용자 가입 현황 확인")
print("=" * 60)

# Try to connect using pymysql directly
try:
    import pymysql
    
    # Get connection info from environment
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = int(os.getenv("DB_PORT", "3306"))
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME", "ssmaker_auth")
    
    print(f"\n연결 정보:")
    print(f"  Host: {db_host}")
    print(f"  Port: {db_port}")
    print(f"  User: {db_user}")
    print(f"  DB: {db_name}")
    print(f"  Password: {'설정됨' if db_password else '없음'}")
    
    if not db_password:
        print("\n❌ DB_PASSWORD가 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)
    
    print("\n데이터베이스 연결 중...")
    
    conn = pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
        charset='utf8mb4'
    )
    
    cursor = conn.cursor()
    
    # 1. 전체 사용자 수 확인
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    print(f"\n📊 전체 사용자 수: {total_users}명")
    
    # 2. 오늘 가입한 사용자 확인 (UTC 기준 - KST는 +9시간)
    # 한국 시간 기준 오늘 00:00 = UTC 전날 15:00
    today_kst = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = today_kst - timedelta(hours=9)
    
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE created_at >= %s",
        (today_utc,)
    )
    today_users = cursor.fetchone()[0]
    print(f"📅 오늘 가입한 사용자 (KST 기준): {today_users}명")
    
    # 3. 최근 7일간 가입한 사용자
    week_ago = datetime.now() - timedelta(days=7)
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE created_at >= %s",
        (week_ago,)
    )
    week_users = cursor.fetchone()[0]
    print(f"📅 최근 7일간 가입: {week_users}명")
    
    # 4. 최근 가입한 10명 목록
    print(f"\n📋 최근 가입한 사용자 목록 (최대 20명):")
    print("-" * 80)
    cursor.execute("""
        SELECT id, username, name, phone, created_at, user_type 
        FROM users 
        ORDER BY created_at DESC 
        LIMIT 20
    """)
    
    rows = cursor.fetchall()
    for row in rows:
        user_id, username, name, phone, created_at, user_type = row
        # UTC to KST
        created_kst = created_at + timedelta(hours=9) if created_at else None
        created_str = created_kst.strftime("%Y-%m-%d %H:%M:%S") if created_kst else "-"
        print(f"  ID:{user_id:3d} | {username:15s} | {name or '-':10s} | {phone or '-':13s} | {created_str} | {user_type}")
    
    print("-" * 80)
    
    # 5. 일별 가입 통계 (최근 7일)
    print(f"\n📈 일별 가입 통계 (최근 7일):")
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count 
        FROM users 
        WHERE created_at >= %s
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """, (week_ago,))
    
    daily_stats = cursor.fetchall()
    for date, count in daily_stats:
        print(f"  {date}: {count}명")
    
    conn.close()
    print("\n✅ 데이터베이스 연결 종료")
    
except ImportError:
    print("❌ pymysql 모듈이 설치되지 않았습니다.")
    print("   pip install pymysql")
except pymysql.Error as e:
    print(f"❌ 데이터베이스 연결 오류: {e}")
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
