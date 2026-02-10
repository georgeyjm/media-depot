from typing import Optional

from sqlalchemy import Integer, String, Text, BigInteger, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin
from app.models.enums import MediaType


class MediaAsset(Base, TimestampMixin):
    '''
    Table for physical media asset files.
    '''
    __tablename__ = 'media_assets'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_type: Mapped[MediaType] = mapped_column(nullable=False, default=MediaType.unknown)
    file_format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Original URL from platform
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # File size in bytes
    file_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    post_media_refs: Mapped[list['PostMedia']] = relationship(back_populates='media_asset')
    creator: Mapped[Optional['Creator']] = relationship(back_populates='profile_pic', cascade='all, delete-orphan')  # Profile pics
    post: Mapped[Optional['Post']] = relationship(back_populates='thumbnail', cascade='all, delete-orphan')  # Post thumbnails
    
    # Constraints and indexes
    __table_args__ = (
        Index('ix_media_assets_file_size_checksum', 'file_size', 'checksum_sha256'),
    )
    
    def __repr__(self) -> str:
        return f'<MediaFile {self.media_type}:{self.file_path or self.url}>'

