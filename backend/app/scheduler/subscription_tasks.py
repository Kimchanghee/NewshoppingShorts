# -*- coding: utf-8 -*-
"""
Subscription Scheduler Tasks
구독 스케줄러 작업

만료 처리, 알림 발송 등 주기적 작업을 정의합니다.
독립 실행 또는 APScheduler/Celery 등과 연동 가능
"""
import logging
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

# Database imports (adjust based on your setup)
try:
    from app.database import SessionLocal
except ImportError:
    SessionLocal = None

from app.utils.subscription_manager import (
    process_expired_subscriptions,
    get_users_needing_expiry_notification,
    get_subscription_summary,
)
from app.utils.payment_error_tracker import get_error_count_by_type

logger = logging.getLogger(__name__)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """데이터베이스 세션 컨텍스트 매니저."""
    if SessionLocal is None:
        raise RuntimeError("Database not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def task_process_expired_subscriptions() -> dict:
    """
    만료된 구독을 처리하는 스케줄러 작업.
    권장 실행 주기: 매시간 또는 매일 자정
    
    Returns:
        Result dictionary with processed and failed counts
    """
    logger.info("[Scheduler] Starting expired subscriptions processing...")
    
    try:
        with get_db_session() as db:
            processed, failed = process_expired_subscriptions(db)
            
            result = {
                "task": "process_expired_subscriptions",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "processed": processed,
                "failed": failed,
                "status": "completed",
            }
            
            logger.info(f"[Scheduler] Expired subscriptions processed: {result}")
            return result
    except Exception as e:
        logger.error(f"[Scheduler] Failed to process expired subscriptions: {e}")
        return {
            "task": "process_expired_subscriptions",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "error": str(e),
        }


def task_send_expiry_notifications() -> dict:
    """
    만료 임박 알림을 발송하는 스케줄러 작업.
    권장 실행 주기: 매일 오전 9시 (사용자 시간대)
    
    Returns:
        Result dictionary with notification counts
    """
    logger.info("[Scheduler] Starting expiry notification task...")
    
    notification_days = [7, 3, 1]  # D-7, D-3, D-1
    sent_count = 0
    failed_count = 0
    
    try:
        with get_db_session() as db:
            users_by_days = get_users_needing_expiry_notification(db, notification_days)
            
            for days, users in users_by_days.items():
                for user in users:
                    try:
                        # 알림 발송 (여기서는 로그만, 실제 구현은 이메일/푸시 서비스 연동)
                        _send_expiry_notification(user, days)
                        sent_count += 1
                    except Exception as e:
                        logger.error(
                            f"[Scheduler] Failed to send notification to user={user.id}: {e}"
                        )
                        failed_count += 1
            
            result = {
                "task": "send_expiry_notifications",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "sent": sent_count,
                "failed": failed_count,
                "status": "completed",
            }
            
            logger.info(f"[Scheduler] Expiry notifications sent: {result}")
            return result
    except Exception as e:
        logger.error(f"[Scheduler] Failed to send expiry notifications: {e}")
        return {
            "task": "send_expiry_notifications",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "error": str(e),
        }


def _send_expiry_notification(user, days_remaining: int) -> None:
    """
    만료 알림을 발송합니다 (플레이스홀더).
    
    실제 구현에서는 이메일/푸시 서비스와 연동하세요.
    예: SendGrid, Firebase Cloud Messaging, 카카오 알림톡 등
    """
    # TODO: 실제 알림 서비스 연동
    email = getattr(user, 'email', None)
    user_id = getattr(user, 'id', 'unknown')
    
    if days_remaining == 7:
        message = "구독이 7일 후 만료됩니다. 갱신을 권장합니다."
    elif days_remaining == 3:
        message = "구독이 3일 후 만료됩니다. 서비스 이용을 위해 갱신해주세요."
    elif days_remaining == 1:
        message = "구독이 내일 만료됩니다! 지금 바로 갱신하세요."
    else:
        message = f"구독이 {days_remaining}일 후 만료됩니다."
    
    logger.info(
        f"[Notification] Expiry alert: user={user_id}, email={email}, "
        f"days_remaining={days_remaining}, message={message}"
    )


def task_generate_payment_health_report() -> dict:
    """
    결제 시스템 헬스 리포트를 생성하는 스케줄러 작업.
    권장 실행 주기: 매일 또는 매시간
    
    Returns:
        Result dictionary with error statistics
    """
    logger.info("[Scheduler] Generating payment health report...")
    
    try:
        with get_db_session() as db:
            error_counts = get_error_count_by_type(db, hours=24)
            
            # 경고 임계값 체크
            alerts = []
            if error_counts.get("gateway_error", 0) > 10:
                alerts.append("High gateway error rate detected")
            if error_counts.get("timeout", 0) > 20:
                alerts.append("High timeout rate detected")
            if error_counts.get("auth_error", 0) > 5:
                alerts.append("Authentication errors detected")
            
            result = {
                "task": "payment_health_report",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "error_counts_24h": error_counts,
                "alerts": alerts,
                "status": "completed",
            }
            
            if alerts:
                logger.warning(f"[Scheduler] Payment health alerts: {alerts}")
            else:
                logger.info(f"[Scheduler] Payment health report: {result}")
            
            return result
    except Exception as e:
        logger.error(f"[Scheduler] Failed to generate payment health report: {e}")
        return {
            "task": "payment_health_report",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "error": str(e),
        }


# APScheduler 또는 Celery 연동 예시
def setup_scheduler(scheduler):
    """
    APScheduler와 연동하여 작업을 등록합니다.
    
    Example usage with APScheduler:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        setup_scheduler(scheduler)
        scheduler.start()
    """
    # 매 시간 만료 처리
    scheduler.add_job(
        task_process_expired_subscriptions,
        'cron',
        hour='*',
        minute=0,
        id='process_expired_subscriptions',
        replace_existing=True,
    )
    
    # 매일 09:00 (KST) 만료 알림
    scheduler.add_job(
        task_send_expiry_notifications,
        'cron',
        hour=0,  # UTC 00:00 = KST 09:00
        minute=0,
        id='send_expiry_notifications',
        replace_existing=True,
    )
    
    # 매 시간 헬스 리포트
    scheduler.add_job(
        task_generate_payment_health_report,
        'cron',
        hour='*',
        minute=30,
        id='payment_health_report',
        replace_existing=True,
    )
    
    logger.info("[Scheduler] All subscription tasks scheduled")


# CLI 실행용
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    if len(sys.argv) > 1:
        task_name = sys.argv[1]
        
        if task_name == "expire":
            result = task_process_expired_subscriptions()
        elif task_name == "notify":
            result = task_send_expiry_notifications()
        elif task_name == "health":
            result = task_generate_payment_health_report()
        else:
            print(f"Unknown task: {task_name}")
            print("Available tasks: expire, notify, health")
            sys.exit(1)
        
        print(result)
    else:
        print("Usage: python -m app.scheduler.subscription_tasks <task_name>")
        print("Available tasks: expire, notify, health")
