from typing import Optional

from sqlalchemy import Integer, String, Text, BigInteger
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

    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # Original URL from platform
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # File size in bytes
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    post_media_refs: Mapped[list['PostMedia']] = relationship(back_populates='media_asset')
    
    def __repr__(self) -> str:
        return f'<MediaFile {self.file_type}:{self.file_path or self.url}>'

