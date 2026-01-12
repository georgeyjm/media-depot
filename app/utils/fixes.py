from sqlalchemy.orm import Session

from app.models import MediaAsset
from app.utils.db import to_relative_media_path


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
