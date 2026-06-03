from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config.config import get_settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    cfg = get_settings().database
    engine = create_engine(
        cfg.url,
        pool_size=cfg.pool_size,
        max_overflow=cfg.max_overflow,
        echo=cfg.echo,
        future=True,
    )
    @event.listens_for(engine, "connect")
    def _set_encoding(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("SET client_encoding TO 'UTF8'")
        cursor.close()
    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"DB connection failed: {exc}")
        return False
