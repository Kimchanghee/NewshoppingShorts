#!/usr/bin/env python3
"""Run database migration using the backend's database module."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# 환경 변수 설정 (기존 값 사용 또는 사용자 입력 요청)
# 환경 변수가 설정되지 않았을 경우에만 기본값 사용
import getpass


def get_env_or_input(env_var, prompt, default=None, secret=False):
    """환경 변수 또는 사용자 입력으로 값 가져오기"""
    value = os.getenv(env_var)
    if value:
        print(f"✓ {env_var} 환경 변수 사용됨")
        return value

    if default and os.getenv("CI", "false").lower() == "true":
        # CI 환경에서는 기본값 사용
        print(f"⚠️ CI 환경에서 {env_var} 기본값 사용")
        return default

    # 사용자 입력 요청
    if secret:
        value = getpass.getpass(prompt + f" (기본값: {default}): ")
    else:
        value = input(prompt + f" (기본값: {default}): ")

    if not value.strip():
        value = default

    return value


# 데이터베이스 연결 정보
print("\n🔧 데이터베이스 연결 설정")
print("=" * 50)

db_host = get_env_or_input("DB_HOST", "데이터베이스 호스트", "127.0.0.1")
db_port = get_env_or_input("DB_PORT", "데이터베이스 포트", "3307")
db_user = get_env_or_input("DB_USER", "데이터베이스 사용자명", "migration_admin")
db_password = get_env_or_input(
    "DB_PASSWORD", "데이터베이스 비밀번호", "MigAdmin123!", secret=True
)
db_name = get_env_or_input("DB_NAME", "데이터베이스 이름", "ssmaker_auth")

os.environ["DB_HOST"] = db_host
os.environ["DB_PORT"] = db_port
os.environ["DB_USER"] = db_user
os.environ["DB_PASSWORD"] = db_password
os.environ["DB_NAME"] = db_name
os.environ["ENVIRONMENT"] = "development"  # 마이그레이션은 개발 모드로 실행

# Cloud SQL 연결 이름 초기화
os.environ["CLOUD_SQL_CONNECTION_NAME"] = ""

# JWT 및 API 키 설정 (필수 아님 - 마이그레이션용 더미 값)
print("\n🔑 JWT 및 API 키 설정 (마이그레이션용)")
print("=" * 50)
print("⚠️  참고: 마이그레이션에는 더미 값만 필요합니다.")
print("    실제 운영 환경에서는 반드시 안전한 환경 변수를 사용하세요.")

jwt_secret = get_env_or_input(
    "JWT_SECRET_KEY", "JWT 비밀 키", "dummy_migration_key_" + os.urandom(16).hex()[:32]
)
admin_key = get_env_or_input(
    "ADMIN_API_KEY", "관리자 API 키", "dummy_admin_key_" + os.urandom(16).hex()[:32]
)
ssmaker_key = get_env_or_input(
    "SSMAKER_API_KEY",
    "SSMaker API 키",
    "dummy_ssmaker_key_" + os.urandom(16).hex()[:32],
)

os.environ["JWT_SECRET_KEY"] = jwt_secret
os.environ["ADMIN_API_KEY"] = admin_key
os.environ["SSMAKER_API_KEY"] = ssmaker_key

print("\n✅ 환경 변수 설정 완료")
print("=" * 50)


def migrate_subscription_system(conn, text):
    """
    Migrate database for subscription system:
    1. Create subscription_requests table
    2. Add user_type column to users table
    3. Update existing users with user_type
    """
    print("\n[*] Running subscription system migration...")

    # 1. Create subscription_requests table
    print("  - Creating subscription_requests table...")
    conn.execute(
        text("""
        CREATE TABLE IF NOT EXISTS subscription_requests (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            status ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING',
            requested_work_count INT DEFAULT 100,
            message TEXT,
            admin_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP NULL,
            reviewed_by INT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    )
    conn.commit()

    # Check if index exists before creating
    result = conn.execute(
        text("""
        SELECT COUNT(*) FROM information_schema.statistics
        WHERE table_schema = DATABASE()
        AND table_name = 'subscription_requests'
        AND index_name = 'idx_subscription_requests_status'
    """)
    )
    if result.fetchone()[0] == 0:
        conn.execute(
            text(
                "CREATE INDEX idx_subscription_requests_status ON subscription_requests(status)"
            )
        )
        conn.commit()

    result = conn.execute(
        text("""
        SELECT COUNT(*) FROM information_schema.statistics
        WHERE table_schema = DATABASE()
        AND table_name = 'subscription_requests'
        AND index_name = 'idx_subscription_requests_user_id'
    """)
    )
    if result.fetchone()[0] == 0:
        conn.execute(
            text(
                "CREATE INDEX idx_subscription_requests_user_id ON subscription_requests(user_id)"
            )
        )
        conn.commit()

    print("  [OK] subscription_requests table created!")

    # 2. Add user_type column to users table if not exists
    print("  - Checking user_type column in users table...")
    result = conn.execute(
        text("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = DATABASE()
        AND table_name = 'users'
        AND column_name = 'user_type'
    """)
    )
    if result.fetchone()[0] == 0:
        print("  - Adding user_type column...")
        conn.execute(
            text("""
            ALTER TABLE users
            ADD COLUMN user_type ENUM('trial', 'subscriber', 'admin') DEFAULT 'trial'
        """)
        )
        conn.commit()

        # 3. Update existing users with user_type
        print("  - Updating existing users with user_type...")

        # 무제한 구독자 설정
        conn.execute(
            text("""
            UPDATE users SET user_type = 'subscriber' WHERE work_count = -1
        """)
        )

        # 체험판 사용자 설정 (work_count > 0이고 -1이 아닌 경우)
        conn.execute(
            text("""
            UPDATE users 
            SET user_type = 'trial' 
            WHERE work_count > 0 
            AND work_count != -1
            AND (user_type IS NULL OR user_type = 'trial')
        """)
        )

        # 작업 횟수가 0인 사용자 (만료된 체험판) 설정
        conn.execute(
            text("""
            UPDATE users 
            SET user_type = 'trial' 
            WHERE work_count = 0
            AND (user_type IS NULL OR user_type = 'trial')
        """)
        )

        # 관리자 사용자 확인 및 설정 (선택사항 - 필요시 수동 설정)
        print("  - 관리자 사용자는 수동으로 user_type = 'admin'으로 설정해주세요.")

        conn.commit()
        print("  [OK] user_type column added and updated!")
    else:
        print("  [OK] user_type column already exists!")

    print("[OK] Subscription system migration completed!")


def main():
    print("[*] Initializing database connection...")

    try:
        from app.database import init_db, engine
        from sqlalchemy import text

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("[OK] Database connection successful!")

            # Show existing tables
            result = conn.execute(text("SHOW TABLES"))
            tables = result.fetchall()
            print("\n=== Current Tables ===")
            for t in tables:
                print(f"  - {t[0]}")

        # Run init_db to create all tables
        print("\n[*] Creating tables...")
        init_db()
        print("[OK] Tables created/verified!")

        # Verify registration_requests table
        with engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES LIKE 'registration_requests'"))
            if result.fetchone():
                print("\n[OK] registration_requests table exists!")
                result = conn.execute(
                    text("SELECT COUNT(*) FROM registration_requests")
                )
                count = result.fetchone()[0]
                print(f"     Record count: {count}")

                # Show structure
                result = conn.execute(text("DESC registration_requests"))
                print("\n=== Table Structure ===")
                for row in result:
                    print(f"  {row[0]}: {row[1]}")
            else:
                print("\n[ERROR] registration_requests table was not created!")
                return 1

        # Run subscription system migration
        with engine.connect() as conn:
            migrate_subscription_system(conn, text)

        print("\n[OK] Migration completed successfully!")
        return 0

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
