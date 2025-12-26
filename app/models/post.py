from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, DateTime, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin
from app.models.enums import PostType


class Post(Base, TimestampMixin):
    __tablename__ = 'posts'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey('platforms.id', ondelete='CASCADE'), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    platform_post_id: Mapped[str] = mapped_column(String(200), nullable=False)  # Platform-native post ID
    post_type: Mapped[PostType] = mapped_column(nullable=False, default=PostType.unknown)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)  # Post full URL
    share_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # Shortened URL for sharing (if available)
    
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    caption_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # Thumbnail URL
    # thumbnail_local_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # Local cached thumbnail
    
    # Relationships
    platform: Mapped['Platform'] = relationship(back_populates='posts')
    account: Mapped['Account'] = relationship(back_populates='posts')
    media_items: Mapped[list['PostMedia']] = relationship(back_populates='post', cascade='all, delete-orphan')
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('platform_id', 'platform_post_id', name='uq_platform_post'),
        Index('ix_posts_platform_id', 'platform_id', 'platform_post_id'),
        Index('ix_posts_account_published', 'account_id', 'platform_created_at'),
    )
    
    def __repr__(self) -> str:
        return f'<Post {self.platform_post_id}:{self.title or "Untitled"}>'

