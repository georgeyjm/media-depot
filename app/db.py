from __future__ import annotations

from typing import Annotated
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from fastapi import Depends

from app.config import settings


engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    '''
    FastAPI dependency that provides a per-request DB session.
    Ensures rollback on error and always closes.
    '''
    db = SessionLocal()
    try:
        yield db
        # Note: commit should be done explicitly by route/service
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def healthcheck_db() -> bool:
    '''Simple DB connectivity check.'''
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    return True


SessionDep = Annotated[Session, Depends(get_db)]
