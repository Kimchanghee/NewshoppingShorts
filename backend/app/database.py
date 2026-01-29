import logging
from sqlalchemy import create_engine, URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Connection pool configuration
# Using URL.create() instead of f-string to prevent password from appearing in stack traces

# Cloud Run uses Unix socket for Cloud SQL connection
if settings.CLOUD_SQL_CONNECTION_NAME:
    # Unix socket path for Cloud Run
    unix_socket_path = f"/cloudsql/{settings.CLOUD_SQL_CONNECTION_NAME}"
    DATABASE_URL = URL.create(
        "mysql+pymysql",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        query={"unix_socket": unix_socket_path, "charset": "utf8mb4"}
    )
else:
    # TCP connection for local development
    DATABASE_URL = URL.create(
        "mysql+pymysql",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        query={"charset": "utf8mb4"}
    )

engine = create_engine(
    DATABASE_URL,
    pool_size=5,  # Connections in pool
    max_overflow=10,  # Extra connections when pool full
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections every hour
    echo=False,  # Set True for SQL logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Dependency for endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables
    데이터베이스 테이블 초기화
    """
    # Import all models to register them with Base
    from app.models import user, session, login_attempt, registration_request, subscription_request
    Base.metadata.create_all(bind=engine)
