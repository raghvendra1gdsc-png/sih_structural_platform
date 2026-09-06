"""
backend/db/session.py
======================
SQLAlchemy engine factory and session helper for the ingestion pipeline.

Phase 4 will add FastAPI dependency-injection session middleware here.
For Phase 1 (seeding), use the context-manager pattern directly.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Default: read from environment, fall back to docker-compose default
_DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sih_user:sih_password@localhost:5432/weather_db",
)


def engine_from_url(database_url: str = _DEFAULT_DATABASE_URL) -> Engine:
    """
    Create a SQLAlchemy Engine from a database URL.

    Parameters
    ----------
    database_url : str
        PostgreSQL connection string, e.g.
        ``"postgresql://user:pass@host:port/dbname"``

    Returns
    -------
    Engine
    """
    engine = create_engine(
        database_url,
        pool_pre_ping=True,         # verify connection liveness before use
        pool_size=5,
        max_overflow=10,
        echo=False,                 # set True to log SQL
    )
    logger.debug("Created engine for %s", database_url.split("@")[-1])
    return engine


_ENGINE: Engine | None = None


def get_engine(database_url: str = _DEFAULT_DATABASE_URL) -> Engine:
    """Get or create singleton SQLAlchemy Engine."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = engine_from_url(database_url)
    return _ENGINE


@contextmanager
def get_session(database_url: str = _DEFAULT_DATABASE_URL) -> Generator[Session, None, None]:
    """
    Context-manager that yields a SQLAlchemy Session and commits/rolls back.

    Usage
    -----
    with get_session() as session:
        session.add(some_orm_object)
    """
    engine = get_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a SQLAlchemy database session.
    Automatically closes session on request completion.
    """
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()



def verify_postgis(database_url: str = _DEFAULT_DATABASE_URL) -> bool:
    """
    Check that PostGIS extension is available.

    Returns True on success, False on failure (never raises).
    """
    try:
        engine = engine_from_url(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT PostGIS_Version()"))
            version = result.scalar()
            logger.info("PostGIS version: %s", version)
            return True
    except Exception as exc:
        logger.error("PostGIS verification failed: %s", exc)
        return False
