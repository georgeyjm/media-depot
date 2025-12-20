from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel, ConfigDict

from app.models import Base, TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = 'accounts'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey('platforms.id', ondelete='CASCADE'), nullable=False, index=True)
    platform_account_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Platform-native account ID
    username: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    profile_pic_asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey('media_assets.id', ondelete='SET NULL'), nullable=True)
    profile_pic_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # When profile pic was last cached
    # profile_pic_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # Original URL from platform
    
    # Relationships
    platform: Mapped['Platform'] = relationship(back_populates='accounts')
    posts: Mapped[list['Post']] = relationship(back_populates='account', cascade='all, delete-orphan')
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('platform_id', 'platform_account_id', name='uq_platform_account_id'),
        Index('ix_accounts_username', 'platform_id', 'username'),
    )
    
    def __repr__(self) -> str:
        return f'<Account {self.platform.name}:{self.username or self.platform_account_id}>'


# Pydantic schemas for API serialization

class AccountBase(BaseModel):
    '''Base schema for Account.'''
    platform_account_id: str
    username: str
    display_name: Optional[str] = None


class AccountCreate(AccountBase):
    '''Schema for creating a new Account.'''
    platform_id: int
    profile_pic_asset_id: Optional[int] = None  # Optional MediaAsset ID for profile picture


class AccountUpdate(BaseModel):
    '''Schema for updating an Account.'''
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_pic_asset_id: Optional[int] = None  # Set profile pic to existing MediaAsset


class AccountResponse(AccountBase):
    '''Schema for Account API responses.'''
    id: int
    platform_id: int
    profile_pic_asset_id: Optional[int] = None
    profile_pic_updated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
