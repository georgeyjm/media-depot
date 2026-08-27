#!/usr/bin/env python3
'''
Check an imported database against what the current code expects.

There are no Alembic migrations in this project - the schema is whatever
Base.metadata.create_all() produced at the time. A dump taken from an older
copy of the app can therefore be missing columns that today's models require,
and create_all() will NOT add them (it only creates missing tables).

This reports:
  1. row counts per table
  2. tables/columns the models expect but the database lacks (breaks the app)
  3. columns the database has but the models no longer define (harmless)
  4. media_assets rows whose file is missing on disk

Usage:
    docker compose exec api uv run scripts/verify_import.py
    uv run scripts/verify_import.py            # against whatever DATABASE_URL points at
'''

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, func, select

from app.config import settings
from app.db import engine, SessionLocal
from app.models import Base, MediaAsset


def report_row_counts(db) -> None:
    print('Row counts')
    print('-' * 60)
    for table in Base.metadata.sorted_tables:
        try:
            count = db.execute(select(func.count()).select_from(table)).scalar_one()
            print(f'  {table.name:<16} {count:>10,}')
        except Exception as e:
            print(f'  {table.name:<16} {"ERROR":>10}  {e.__class__.__name__}')
    print()


def report_schema_drift() -> bool:
    '''Compare live schema against the models. Returns True if the app would break.'''
    inspector = inspect(engine)
    live_tables = set(inspector.get_table_names())

    missing_tables: list[str] = []
    missing_columns: list[str] = []
    extra_columns: list[str] = []

    for table in Base.metadata.sorted_tables:
        if table.name not in live_tables:
            missing_tables.append(table.name)
            continue
        live_columns = {c['name'] for c in inspector.get_columns(table.name)}
        model_columns = {c.name for c in table.columns}
        for name in sorted(model_columns - live_columns):
            missing_columns.append(f'{table.name}.{name}')
        for name in sorted(live_columns - model_columns):
            extra_columns.append(f'{table.name}.{name}')

    print('Schema comparison (models vs database)')
    print('-' * 60)
    if not missing_tables and not missing_columns and not extra_columns:
        print('  No differences.')
    if missing_tables:
        print('  MISSING TABLES (app will break):')
        for name in missing_tables:
            print(f'    - {name}')
    if missing_columns:
        print('  MISSING COLUMNS (app will break):')
        for name in missing_columns:
            print(f'    - {name}')
    if extra_columns:
        print('  Extra columns in database (harmless, from an older schema):')
        for name in extra_columns:
            print(f'    - {name}')
    print()
    return bool(missing_tables or missing_columns)


def report_missing_media(db, sample: int = 10) -> int:
    '''Check that every media asset's file actually exists under MEDIA_ROOT_DIR.'''
    root = settings.MEDIA_ROOT_DIR
    print(f'Media files (MEDIA_ROOT_DIR = {root.resolve()})')
    print('-' * 60)

    total = 0
    missing: list[str] = []
    for (file_path,) in db.execute(select(MediaAsset.file_path)):
        if not file_path:
            continue
        total += 1
        if not (root / file_path).exists():
            missing.append(file_path)

    present = total - len(missing)
    print(f'  {present:,} of {total:,} asset files present on disk')
    if missing:
        print(f'  {len(missing):,} MISSING - first {min(sample, len(missing))}:')
        for file_path in missing[:sample]:
            print(f'    - {file_path}')
        if len(missing) > sample:
            print(f'    ... and {len(missing) - sample:,} more')
    print()
    return len(missing)


def main() -> int:
    print()
    print(f'Database: {engine.url.render_as_string(hide_password=True)}')
    print()

    db = SessionLocal()
    try:
        broken = report_schema_drift()
        report_row_counts(db)
        missing_media = report_missing_media(db)
    finally:
        db.close()

    if broken:
        print('RESULT: schema is missing things the code needs - see above.')
        print('The usual cause is a dump taken before a model change. Those columns')
        print('must be added by hand (ALTER TABLE) before the app will work.')
        return 1
    if missing_media:
        print('RESULT: schema is fine, but some media files are not on disk yet.')
        print('Copy the old media/ folder into this project, preserving subfolders.')
        return 0
    print('RESULT: all good.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
