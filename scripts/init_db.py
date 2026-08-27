#!/usr/bin/env python3
'''
Create database tables and seed the platform rows.

Runs as a one-shot 'migrate' service in docker compose, before the api and
worker start, so neither of them races the other to create the schema.

Usage:
    uv run scripts/init_db.py
'''

import sys
import time
from pathlib import Path

# Allow running as `python scripts/init_db.py` from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.exc import OperationalError

from app.db import engine, SessionLocal
from app.models import Base
from app.handlers import initialize_platforms


def wait_for_db(attempts: int = 30, delay: float = 1.0) -> None:
    '''Wait for the database to accept connections.'''
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect():
                return
        except OperationalError as e:
            if attempt == attempts:
                raise
            print(f'Database not ready ({attempt}/{attempts}): {e.__class__.__name__}')
            time.sleep(delay)


def main() -> int:
    wait_for_db()

    print('Creating tables ...')
    Base.metadata.create_all(bind=engine)

    print('Seeding platforms ...')
    db = SessionLocal()
    try:
        initialize_platforms(db)
    finally:
        db.close()

    print('Database ready.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
