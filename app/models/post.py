from pathlib import Path
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin
from app.models.enums import PostType, JobStatus


class Post(Base, TimestampMixin):
    __tablename__ = 'posts'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey('platforms.id', ondelete='CASCADE'), nullable=False, index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey('creators.id', ondelete='CASCADE'), nullable=False, index=True)
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
    creator: Mapped['Creator'] = relationship(back_populates='posts')
    media_items: Mapped[list['PostMedia']] = relationship(back_populates='post', cascade='all, delete-orphan')
    jobs: Mapped[list['Job']] = relationship(back_populates='post', cascade='all, delete-orphan')
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('platform_id', 'platform_post_id', name='uq_platform_post'),
        Index('ix_posts_platform_post_id', 'platform_id', 'platform_post_id'),
        Index('ix_posts_creator_published', 'creator_id', 'platform_created_at'),
    )
    
    def __repr__(self) -> str:
        return f'<Post {self.platform_post_id}:{self.title or "Untitled"}>'
    
    def all_media_exists(self) -> bool:
        '''Check if all media items exist on disk.
        
        Returns:
            True if post has media_items and all files exist on disk, False otherwise.
        '''
        if not self.media_items:
            return False  # No media items means nothing exists
        return all(Path(post_media.media_asset.file_path).exists() for post_media in self.media_items)
    
    def has_completed_job(self) -> bool:
        '''Check if there's at least one completed job for this post.
        
        Returns:
            True if post has at least one job with status 'completed', False otherwise.
        '''
        # TODO: Maybe we should only consider the last job?
        return any(job.status == JobStatus.completed for job in self.jobs)
