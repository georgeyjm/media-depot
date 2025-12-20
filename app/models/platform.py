from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel, ConfigDict

from app.models import Base, TimestampMixin


class Platform(Base, TimestampMixin):
    __tablename__ = 'platforms'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., 'YouTube', 'TikTok'
    # api_base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Base URL for platform API
    # is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    accounts: Mapped[list['Account']] = relationship(back_populates='platform', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return f'<Platform {self.name}>'


# Pydantic schemas for API serialization
class PlatformBase(BaseModel):
    '''Base schema for Platform.'''
    name: str
    display_name: str


class PlatformCreate(PlatformBase):
    '''Schema for creating a new Platform.'''
    pass


class PlatformUpdate(BaseModel):
    '''Schema for updating a Platform.'''
    display_name: Optional[str] = None


class PlatformResponse(PlatformBase):
    '''Schema for Platform API responses.'''
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
