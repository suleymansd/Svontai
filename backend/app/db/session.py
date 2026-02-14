"""
Database session management.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )
except ArgumentError as exc:
    raise RuntimeError(
        "Invalid DATABASE_URL. Railway'de DATABASE_URL değişkenini "
        "${{Postgres.DATABASE_URL}} olarak ayarlayın."
    ) from exc

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.
    Ensures the session is properly closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
