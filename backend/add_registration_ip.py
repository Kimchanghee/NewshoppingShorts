import logging
import os
import sys
from sqlalchemy import create_engine, text, URL
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO)
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

def run_migration():
    logger.info("Starting migration...")

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
        engine = create_engine(connection_url, echo=True)

        logger.info(f"Connecting to database at {DB_HOST}:{DB_PORT}...")
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT count(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 'users' AND COLUMN_NAME = 'registration_ip'"
            ), {"db": DB_NAME})

            exists = result.scalar() > 0

            if exists:
                logger.info("[OK] registration_ip column already exists in users table")
            else:
                logger.info("Adding registration_ip column...")
                sql = "ALTER TABLE users ADD COLUMN registration_ip VARCHAR(45) NULL"
                conn.execute(text(sql))
                conn.commit()
                logger.info("[OK] Successfully added registration_ip column to users table")

    except SQLAlchemyError as e:
        logger.error(f"[FAIL] Database error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
