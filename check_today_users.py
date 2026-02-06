import logging
import os
import sys
from sqlalchemy import create_engine, text, URL
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Database configuration from environment variables
DB_USER = os.environ.get("DB_USER", "ssmaker_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_NAME = os.environ.get("DB_NAME", "ssmaker_auth")

if not DB_PASSWORD:
    logger.error("DB_PASSWORD environment variable is required")
    sys.exit(1)

def check_today_users():
    connection_url = URL.create(
        "mysql+pymysql",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        query={"charset": "utf8mb4"}
    )
    
    try:
        engine = create_engine(connection_url)
        with engine.connect() as conn:
            # KST 기준 오늘 날짜 계산
            kst = pytz.timezone('Asia/Seoul')
            now_kst = datetime.now(kst)
            start_of_day = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # UTC로 변환 (DB는 보통 UTC 저장)
            start_of_day_utc = start_of_day.astimezone(pytz.UTC)
            
            logger.info(f"🔍 조회 기준 시간 (KST): {start_of_day} ~ 현재")
            logger.info(f"   (UTC 변환 시간): {start_of_day_utc.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1. 오늘 가입한 유저 조회
            logger.info("\n📋 [오늘 가입 성공 유저 목록]")
            result = conn.execute(text("""
                SELECT id, username, email, created_at, registration_ip 
                FROM users 
                WHERE created_at >= :start_date
                ORDER BY created_at DESC
            """), {"start_date": start_of_day_utc})
            
            users = result.fetchall()
            if users:
                for u in users:
                    # UTC 시간을 KST로 변환하여 출력
                    created_at_kst = u.created_at.replace(tzinfo=pytz.UTC).astimezone(kst)
                    logger.info(f" - ID: {u.id} | {u.username} | {u.email} | 가입시간: {created_at_kst.strftime('%H:%M:%S')} | IP: {u.registration_ip}")
            else:
                logger.info(" -> ❌ 오늘 가입한 유저가 없습니다.")
                
            # 2. 최근 가입 요청 (Pending 등) 조회
            logger.info("\n📋 [오늘 들어온 구독/가입 요청]")
            result_req = conn.execute(text("""
                SELECT id, username, status, created_at 
                FROM registration_requests 
                WHERE created_at >= :start_date
                ORDER BY created_at DESC
            """), {"start_date": start_of_day_utc})
            
            reqs = result_req.fetchall()
            if reqs:
                for r in reqs:
                    created_at_kst = r.created_at.replace(tzinfo=pytz.UTC).astimezone(kst)
                    logger.info(f" - 요청ID: {r.id} | {r.username} | 상태: {r.status} | 시간: {created_at_kst.strftime('%H:%M:%S')}")
            else:
                logger.info(" -> ❌ 오늘 들어온 가입 요청도 없습니다.")

    except SQLAlchemyError as e:
        logger.error(f"[FAIL] Database error: {e}")

if __name__ == "__main__":
    check_today_users()
