import logging
import sys
import os
from sqlalchemy import text

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_schema():
    with engine.connect() as conn:
        # 1. Update users table
        try:
            logger.info("Updating users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL"))
            logger.info("Added email column to users")
        except Exception as e:
            if "Duplicate column" in str(e) or "1060" in str(e):
                logger.info("email column already exists in users")
            else:
                logger.error(f"Error adding email to users: {e}")

        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(50) NULL"))
            logger.info("Added phone column to users")
        except Exception as e:
            if "Duplicate column" in str(e) or "1060" in str(e):
                logger.info("phone column already exists in users")
            else:
                logger.error(f"Error adding phone to users: {e}")

        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR(100) NULL"))
            logger.info("Added name column to users")
        except Exception as e:
            if "Duplicate column" in str(e) or "1060" in str(e):
                logger.info("name column already exists in users")
            else:
                logger.error(f"Error adding name to users: {e}")

        # 2. Update registration_requests table
        try:
            logger.info("Updating registration_requests table...")
            conn.execute(text("ALTER TABLE registration_requests ADD COLUMN email VARCHAR(255) NULL"))
            logger.info("Added email column to registration_requests")
        except Exception as e:
            if "Duplicate column" in str(e) or "1060" in str(e):
                logger.info("email column already exists in registration_requests")
            else:
                logger.error(f"Error adding email to registration_requests: {e}")
        
        conn.commit()
        logger.info("Schema update completed.")

if __name__ == "__main__":
    update_schema()
