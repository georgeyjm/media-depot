import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import MediaAsset
from app.utils.db import to_relative_media_path, to_absolute_media_path
from app.utils.helpers import sanitize_filename


def migrate_media_paths_to_relative(db: Session) -> int:
    '''
    Migrate all MediaAsset file_path values from absolute to relative paths.

    Returns:
        Number of records updated.
    '''
    updated = 0
    media_assets = db.query(MediaAsset).all()

    for asset in media_assets:
        relative_path = to_relative_media_path(asset.file_path)
        if relative_path != asset.file_path:
            asset.file_path = relative_path
            updated += 1

    if updated:
        db.commit()

    return updated


def sanitize_media_filenames(db: Session) -> tuple[int, list[str]]:
    '''
    Rename files with URL-unsafe characters and update database records.

    Returns:
        Tuple of (number of files renamed, list of error messages).
    '''
    # Pattern matching URL-unsafe characters (same as in sanitize_filename)
    URL_UNSAFE_PATTERN = re.compile(r'[<>:"/\\|?*#%&+=;@!$\'(),]')
    
    renamed = 0
    errors = []
    media_assets = db.query(MediaAsset).all()

    for asset in media_assets:
        relative_path = Path(asset.file_path)
        filename = relative_path.name

        # Check if filename contains URL-unsafe characters
        if not URL_UNSAFE_PATTERN.search(filename):
            continue

        # Generate new sanitized filename
        stem = relative_path.stem
        suffix = relative_path.suffix
        new_filename = sanitize_filename(stem) + suffix
        new_relative_path = relative_path.parent / new_filename

        # Get absolute paths
        old_absolute = to_absolute_media_path(relative_path)
        new_absolute = to_absolute_media_path(new_relative_path)

        # Check if source file exists
        if not old_absolute.exists():
            errors.append(f'Source file not found: {old_absolute}')
            continue

        # Handle filename conflicts
        if new_absolute.exists() and new_absolute != old_absolute:
            # Append short UUID to make unique
            unique_suffix = uuid.uuid4().hex[:8]
            new_filename = f'{sanitize_filename(stem)}_{unique_suffix}{suffix}'
            new_relative_path = relative_path.parent / new_filename
            new_absolute = to_absolute_media_path(new_relative_path)

        # Rename the file
        try:
            old_absolute.rename(new_absolute)
            asset.file_path = str(new_relative_path)
            renamed += 1
        except OSError as e:
            errors.append(f'Failed to rename {old_absolute}: {e}')

    if renamed:
        db.commit()

    return renamed, errors
