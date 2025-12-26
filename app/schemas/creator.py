from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CreatorBase(BaseModel):
    '''Base schema for Creator.'''
    platform_account_id: str
    username: str
    display_name: Optional[str] = None


class CreatorCreate(CreatorBase):
    '''Schema for creating a new Creator.'''
    platform_id: int
    profile_pic_asset_id: Optional[int] = None  # Optional MediaAsset ID for profile picture


class CreatorUpdate(BaseModel):
    '''Schema for updating a Creator.'''
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_pic_asset_id: Optional[int] = None  # Set profile pic to existing MediaAsset


class CreatorResponse(CreatorBase):
    '''Schema for Creator API responses.'''
    id: int
    platform_id: int
    profile_pic_asset_id: Optional[int] = None
    profile_pic_updated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


