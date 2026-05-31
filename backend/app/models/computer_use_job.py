from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.sql import func
import enum

from app.database import Base


class ComputerUseJobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComputerUseJob(Base):
    """
    Centralized computer-use job queue item.

    Backed by DB to support multi-process workers and auditability.
    """

    __tablename__ = "computer_use_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    scope = Column(String(64), nullable=False, default="all")
    step_id = Column(String(96), nullable=True)
    step_title = Column(String(200), nullable=True)
    prompt = Column(Text, nullable=False)

    status = Column(
        SQLEnum(ComputerUseJobStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ComputerUseJobStatus.QUEUED,
        index=True,
    )
    attempt_count = Column(Integer, nullable=False, default=0)
    worker_id = Column(String(128), nullable=True)

    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

