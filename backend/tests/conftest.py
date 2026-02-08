# -*- coding: utf-8 -*-
"""
Pytest Configuration for Backend Tests

Common fixtures and setup for FastAPI backend tests.
"""

import sys
from pathlib import Path

# Add backend root to path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db_session():
    """
    Mock database session for unit tests.
    Use this when testing functions that need a db session
    but don't need actual database operations.
    """
    class MockSession:
        def __init__(self):
            self._added = []
            self._committed = False

        def add(self, obj):
            self._added.append(obj)

        def commit(self):
            self._committed = True

        def refresh(self, obj):
            pass

        def query(self, model):
            return MockQuery(model)

        def close(self):
            pass

    class MockQuery:
        def __init__(self, model):
            self.model = model
            self._filters = []

        def filter(self, *args):
            self._filters.extend(args)
            return self

        def first(self):
            return None

        def all(self):
            return []

    return MockSession()


@pytest.fixture
def sample_payment_data():
    """Sample payment session data for tests"""
    return {
        "payment_id": "test_payment_abc123",
        "plan_id": "pro_1month",
        "user_id": "user_123",
        "status": "pending",
        "amount": 190000,
    }
