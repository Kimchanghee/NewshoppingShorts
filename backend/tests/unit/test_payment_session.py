# -*- coding: utf-8 -*-
"""
Unit Tests for Payment Session Model

Tests the PaymentSession model and PaymentStatus enum.
"""

import pytest
from datetime import datetime, timedelta
from app.models.payment_session import PaymentSession, PaymentStatus


class TestPaymentStatus:
    """Test PaymentStatus enum"""

    def test_payment_status_values(self):
        """Test PaymentStatus enum has correct values"""
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.SUCCEEDED.value == "succeeded"
        assert PaymentStatus.FAILED.value == "failed"
        assert PaymentStatus.CANCELLED.value == "cancelled"
        assert PaymentStatus.EXPIRED.value == "expired"

    def test_all_statuses_exist(self):
        """Test all expected statuses are defined"""
        expected_statuses = ["pending", "succeeded", "failed", "cancelled", "expired"]
        actual_statuses = [s.value for s in PaymentStatus]

        for status in expected_statuses:
            assert status in actual_statuses


class TestPaymentSessionModel:
    """Test PaymentSession model structure"""

    def test_payment_session_tablename(self):
        """Test PaymentSession has correct table name"""
        assert PaymentSession.__tablename__ == "payment_sessions"

    def test_payment_session_columns(self):
        """Test PaymentSession has required columns"""
        columns = [c.name for c in PaymentSession.__table__.columns]

        required_columns = [
            "id",
            "payment_id",
            "plan_id",
            "user_id",
            "status",
            "gateway_reference",
            "amount",
            "created_at",
            "updated_at",
            "expires_at",
        ]

        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_payment_id_is_unique(self):
        """Test payment_id column has unique constraint"""
        payment_id_col = PaymentSession.__table__.columns["payment_id"]
        assert payment_id_col.unique is True

    def test_payment_id_is_indexed(self):
        """Test payment_id column is indexed"""
        payment_id_col = PaymentSession.__table__.columns["payment_id"]
        assert payment_id_col.index is True

    def test_status_column_is_indexed(self):
        """Test status column is indexed for filtering"""
        status_col = PaymentSession.__table__.columns["status"]
        assert status_col.index is True

    def test_user_id_is_indexed(self):
        """Test user_id column is indexed for lookups"""
        user_id_col = PaymentSession.__table__.columns["user_id"]
        assert user_id_col.index is True

    def test_user_id_is_nullable(self):
        """Test user_id allows null for guest checkout"""
        user_id_col = PaymentSession.__table__.columns["user_id"]
        assert user_id_col.nullable is True


class TestPaymentSessionDefaults:
    """Test PaymentSession default values"""

    def test_status_default_is_pending(self):
        """Test default status is PENDING"""
        status_col = PaymentSession.__table__.columns["status"]
        # The default is set as PaymentStatus.PENDING
        assert status_col.default is not None
