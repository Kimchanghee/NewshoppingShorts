import logging
from sqlalchemy import create_engine, URL
from sqlalchemy.engine import make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.configuration import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Connection pool configuration
# Using URL.create() instead of f-string to prevent password from appearing in stack traces

def _database_url_from_settings():
    """Return a database URL for Supabase PostgreSQL or legacy MySQL."""
    if settings.DATABASE_URL:
        raw_url = settings.DATABASE_URL.strip()
        if raw_url.startswith("postgres://"):
            raw_url = raw_url.replace("postgres://", "postgresql://", 1)
        if raw_url.startswith("postgresql://"):
            raw_url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)

        url = make_url(raw_url)
        if url.get_backend_name() == "postgresql" and "sslmode" not in url.query:
            url = url.update_query_dict({"sslmode": "require"})
        return url

    if settings.CLOUD_SQL_CONNECTION_NAME:
        return URL.create(
            "mysql+pymysql",
            username=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            query={
                "unix_socket": f"/cloudsql/{settings.CLOUD_SQL_CONNECTION_NAME}",
                "charset": "utf8mb4",
            },
        )

    return URL.create(
        "mysql+pymysql",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        query={"charset": "utf8mb4"},
    )


DATABASE_URL = _database_url_from_settings()

connect_args = {}
if DATABASE_URL.get_backend_name() == "postgresql":
    # Supabase's PgBouncer pooler can reuse prepared-statement names across
    # logical sessions; disable psycopg's automatic prepare cache.
    connect_args["prepare_threshold"] = None

engine = create_engine(
    DATABASE_URL,
    pool_size=5,  # Connections in pool
    max_overflow=10,  # Extra connections when pool full
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections every hour
    connect_args=connect_args,
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
    from app.models import (
        user,
        session,
        login_attempt,
        registration_request,
        subscription_request,
        payment_session,
        user_log,
        computer_use_job,
        user_settings,
    )
    from app.models import billing  # 빌링키 및 정기결제 모델
    Base.metadata.create_all(bind=engine)
