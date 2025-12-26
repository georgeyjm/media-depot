from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MetadataJSONMixin:
    # Use JSONB for PostgreSQL; if using MySQL/SQLite instead, use sqlalchemy.JSON instead
    metadata_: Mapped[dict[str, Any]] = mapped_column('metadata', JSONB, default=dict, nullable=False)


# Import and expose all models
from app.models.platform import Platform
from app.models.creator import Creator
from app.models.post import Post
from app.models.post_media import PostMedia
from app.models.media_asset import MediaAsset

__all__ = [
    'Base',
    'TimestampMixin',
    'Platform',
    'Creator',
    'Post',
    'PostMedia',
    'MediaAsset',
]
