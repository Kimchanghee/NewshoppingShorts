import sys
import os
import logging
from sqlalchemy import text

# Setup path so we can import 'app'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # Should be NewshoppingShorts if file is in backend/
# Actually we are in backend/, so parent is NewshoppingShorts.
# But app is inside backend/. So if I run from backend/, sys.path should include backend/.

sys.path.append(current_dir) # Add .../backend/ to path.

try:
    from dotenv import load_dotenv
    load_dotenv() # Load .env into os.environ
except ImportError:
    print("python-dotenv not installed, skipping load_dotenv")

# Set dummy env vars to satisfy Settings validation if missing
# DB credentials should be in .env. If missing, this script will likely fail to connect anyway.
# But we need to satisfy Pydantic to even reach connection step.
# We DO NOT overwrite DB keys here to avoid overriding .env values.

os.environ.setdefault("JWT_SECRET_KEY", "0" * 32)
os.environ.setdefault("ADMIN_API_KEY", "0" * 32)
os.environ.setdefault("SSMAKER_API_KEY", "0" * 32)
# Ensure at least some DB defaults if totally missing? No, let Pydantic complain if DB is missing.
os.environ.setdefault("DB_USER", "root")
os.environ.setdefault("DB_PASSWORD", "")

try:
    from app.database import engine
except ImportError as e:
    # Try adding parent if structure is diff
    sys.path.append(parent_dir)
    try:
        from backend.app.database import engine
    except:
        print(f"Import failed: {e}")
        sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_schema():
    logger.info("Connecting to database...")
    with engine.connect() as conn:
        # 1. Update users table
        columns = [
            ("email", "VARCHAR(255) NULL"),
            ("phone", "VARCHAR(50) NULL"),
            ("name", "VARCHAR(100) NULL"),
            ("current_task", "VARCHAR(255) NULL")
        ]
        
        logger.info("Updating users table...")
        for col, type_def in columns:
            try:
                sql = f"ALTER TABLE users ADD COLUMN {col} {type_def}"
                conn.execute(text(sql))
                logger.info(f"Added {col} column to users")
            except Exception as e:
                # Check for duplicate column error (1060)
                if "1060" in str(e) or "Duplicate column" in str(e):
                    logger.info(f"{col} column already exists in users")
                else:
                    logger.warning(f"Error adding {col} to users: {e}")

        # 2. Update registration_requests table
        try:
            logger.info("Updating registration_requests table...")
            conn.execute(text("ALTER TABLE registration_requests ADD COLUMN email VARCHAR(255) NULL"))
            logger.info("Added email column to registration_requests")
        except Exception as e:
            if "1060" in str(e) or "Duplicate column" in str(e):
                logger.info("email column already exists in registration_requests")
            else:
                logger.warning(f"Error adding email to registration_requests: {e}")
        
        conn.commit()
        logger.info("Schema update completed.")

if __name__ == "__main__":
    update_schema()
