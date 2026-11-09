"""Pytest configuration and fixtures for API tests."""

import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models import Base, User
import app.projects.models
import app.paper_trading.models
import app.discovery.models
import app.analysis.models
from app.database import get_db
from argon2 import PasswordHasher

pytest_plugins = []

# Create a test database engine in /tmp which is writable
TEST_DB_URL = "sqlite:////tmp/test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})


@pytest.fixture(scope="session")
def test_db():
    """Create test database and drop tables before tests."""
    # Create database tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables after tests
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(test_db):
    """Create a database session for each test."""
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def client(db):
    """Create test client with database override."""
    from fastapi.testclient import TestClient
    from app.main import app

    def get_db_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(db):
    """Create authenticated test client with dev user."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth import DEV_USER_EMAIL

    # Create dev user if not exists
    hasher = PasswordHasher()
    try:
        from sqlalchemy import select
        user = db.scalar(select(User).where(User.email == DEV_USER_EMAIL))
        if not user:
            user = User(
                email=DEV_USER_EMAIL,
                password_hash=hasher.hash("dev-password-for-testing"),
                is_active=True,
            )
            db.add(user)
            db.commit()
    except Exception:
        db.rollback()

    client = TestClient(app)
    return client
