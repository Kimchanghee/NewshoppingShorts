#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
사용자 생성 스크립트

사용법:
    python create_user.py <username> <password>

예시:
    python create_user.py testuser test123
"""

import sys
from datetime import datetime, timedelta, timezone
from app.database import SessionLocal
from app.models.user import User
from app.utils.password import hash_password


def create_user(username: str, password: str, subscription_days: int = None):
    """
    새로운 사용자를 데이터베이스에 생성합니다.

    Args:
        username: 사용자명 (고유해야 함)
        password: 평문 비밀번호 (자동으로 해시됨)
        subscription_days: 구독 기간 (일 단위, None = 무제한)
    """
    db = SessionLocal()
    try:
        # 기존 사용자 확인
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"❌ 오류: 사용자 '{username}'이(가) 이미 존재합니다.")
            print(f"   생성일: {existing.created_at}")
            print(f"   활성화 상태: {'활성' if existing.is_active else '비활성'}")
            return False

        # 구독 만료일 계산
        subscription_expires_at = None
        if subscription_days is not None:
            subscription_expires_at = datetime.now(timezone.utc) + timedelta(
                days=subscription_days
            )

        # 새 사용자 생성
        user = User(
            username=username,
            password_hash=hash_password(password),
            is_active=True,
            subscription_expires_at=subscription_expires_at,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"✅ 사용자 '{username}' 생성 완료!")
        print(f"   사용자 ID: {user.id}")
        print(f"   생성일: {user.created_at}")
        if subscription_expires_at:
            print(f"   구독 만료일: {subscription_expires_at} ({subscription_days}일)")
        else:
            print(f"   구독: 무제한")

        return True

    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()


def list_users():
    """모든 사용자 목록을 출력합니다."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("등록된 사용자가 없습니다.")
            return

        print(f"\n총 {len(users)}명의 사용자:")
        print("-" * 80)
        print(f"{'ID':<5} {'사용자명':<20} {'활성':<6} {'구독 만료일':<20} {'마지막 로그인'}")
        print("-" * 80)

        for user in users:
            active = "활성" if user.is_active else "비활성"
            subscription = (
                user.subscription_expires_at.strftime("%Y-%m-%d %H:%M")
                if user.subscription_expires_at
                else "무제한"
            )
            last_login = (
                user.last_login_at.strftime("%Y-%m-%d %H:%M")
                if user.last_login_at
                else "없음"
            )
            print(f"{user.id:<5} {user.username:<20} {active:<6} {subscription:<20} {last_login}")

    finally:
        db.close()


def update_password(username: str, new_password: str):
    """사용자 비밀번호를 업데이트합니다."""
    from app.models.session import SessionModel

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ 오류: 사용자 '{username}'을(를) 찾을 수 없습니다.")
            return False

        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)

        # Security: Invalidate all active sessions on password change
        # 보안: 비밀번호 변경 시 모든 활성 세션 무효화
        try:
            invalidated = db.query(SessionModel).filter(
                SessionModel.user_id == user.id,
                SessionModel.is_active == True
            ).update({"is_active": False})
            if invalidated > 0:
                print(f"   ℹ️  {invalidated}개의 활성 세션이 무효화되었습니다.")
        except Exception as session_err:
            # Session invalidation failure should not block password update
            print(f"   ⚠️  세션 무효화 중 오류 (비밀번호는 변경됨): {session_err}")

        db.commit()

        print(f"✅ 사용자 '{username}'의 비밀번호가 업데이트되었습니다.")
        return True

    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()


def main():
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python create_user.py <username> <password> [subscription_days]")
        print("  python create_user.py --list")
        print("  python create_user.py --update <username> <new_password>")
        print("\n예시:")
        print("  python create_user.py testuser test123")
        print("  python create_user.py premium_user pass123 365  # 365일 구독")
        print("  python create_user.py --list")
        print("  python create_user.py --update testuser newpass123")
        sys.exit(1)

    # 사용자 목록 조회
    if sys.argv[1] == "--list":
        list_users()
        return

    # 비밀번호 업데이트
    if sys.argv[1] == "--update":
        if len(sys.argv) != 4:
            print("❌ 오류: --update는 <username> <new_password> 인자가 필요합니다.")
            sys.exit(1)
        update_password(sys.argv[2], sys.argv[3])
        return

    # 사용자 생성
    if len(sys.argv) < 3:
        print("❌ 오류: username과 password가 필요합니다.")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    subscription_days = None

    if len(sys.argv) >= 4:
        try:
            subscription_days = int(sys.argv[3])
        except ValueError:
            print(f"❌ 오류: 구독 기간은 숫자여야 합니다: {sys.argv[3]}")
            sys.exit(1)

    # 비밀번호 강도 검증
    if len(password) < 4:
        print("⚠️  경고: 비밀번호가 너무 짧습니다 (최소 4자 권장).")
        response = input("계속하시겠습니까? (y/N): ")
        if response.lower() != "y":
            print("취소되었습니다.")
            sys.exit(0)

    success = create_user(username, password, subscription_days)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
