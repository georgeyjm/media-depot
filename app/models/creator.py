from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin


class Creator(Base, TimestampMixin):
    __tablename__ = 'creators'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey('platforms.id', ondelete='CASCADE'), nullable=False, index=True)
    platform_account_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Platform-native account ID
    username: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    profile_pic_asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey('media_assets.id', ondelete='SET NULL'), nullable=True)
    profile_pic_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # When profile pic was last cached
    profile_pic_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # Original URL from platform
    
    # Relationships
    platform: Mapped['Platform'] = relationship(back_populates='creators')
    posts: Mapped[list['Post']] = relationship(back_populates='creator', cascade='all, delete-orphan')
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('platform_id', 'platform_account_id', name='uq_platform_account_id'),
        Index('ix_creators_platform_username', 'platform_id', 'username'),
    )
    
    def __repr__(self) -> str:
        return f'<Creator {self.platform.name}:{self.username or self.platform_account_id}>'

