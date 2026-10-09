"""Database plumbing only: engine, session helper, base class.

DATABASE_URL decides the database:
  sqlite:///./tasks.db                          (default, zero setup)
  postgresql+psycopg://user:pass@host:5432/db   (production)
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_url = get_settings().database_url
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Commit on success, roll back on any error, always close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Dev convenience for SQLite. With PostgreSQL, run `alembic upgrade head` instead."""
    import app.models.task  # noqa: F401  (registers the table on Base)

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
