import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client(monkeypatch):
    """
    Provides a FastAPI TestClient backed by an in-memory SQLite database.

    This fixture is intentionally opt-in (only used by tests that request it),
    so existing unit tests remain unaffected.
    """
    from app.core.config import settings

    old_environment = settings.ENVIRONMENT
    old_email_enabled = settings.EMAIL_ENABLED

    settings.ENVIRONMENT = "dev"
    settings.EMAIL_ENABLED = False

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    import app.db.session as session_module
    monkeypatch.setattr(session_module, "engine", engine, raising=False)
    monkeypatch.setattr(session_module, "SessionLocal", TestingSessionLocal, raising=False)

    import app.db as db_module
    monkeypatch.setattr(db_module, "engine", engine, raising=False)
    monkeypatch.setattr(db_module, "SessionLocal", TestingSessionLocal, raising=False)

    from app.db.base import Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from app.main import app
    from app.db.session import get_db

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    settings.ENVIRONMENT = old_environment
    settings.EMAIL_ENABLED = old_email_enabled

