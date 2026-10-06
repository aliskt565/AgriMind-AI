"""
Pytest fixtures.

Tests run against a real Postgres database (`agrimind_test`), not SQLite --
SQLite doesn't support our JSON/UUID/Enum usage identically to Postgres, and
the whole point of testing against the real engine is to catch what an
in-memory substitute would hide.

Each test gets a clean schema: we create all tables before the test session
and drop them after, and each test function runs inside a transaction that
is rolled back afterward for isolation.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "postgresql+psycopg2://postgres:postgres@localhost:5432/agrimind_test"

from app.db.session import Base, get_db
from app.main import app
from fastapi.testclient import TestClient

TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/agrimind_test"
engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """
    Standard SQLAlchemy 'join an external transaction' pattern: the outer
    transaction is never committed (only SAVEPOINTs inside it are), so every
    test is fully isolated regardless of how many times endpoint code calls
    session.commit() internally.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    session.begin_nested()

    from sqlalchemy import event

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def farmer_headers(client):
    """Registers and logs in a fresh farmer, returns Authorization headers."""
    client.post("/api/v1/auth/register", json={
        "email": "test.farmer@example.com",
        "password": "TestPass123",
        "full_name": "Test Farmer",
        "location": "Test Location",
    })
    r = client.post("/api/v1/auth/login", data={"username": "test.farmer@example.com", "password": "TestPass123"})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
