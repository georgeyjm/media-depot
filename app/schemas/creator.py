from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class CreatorBase(BaseModel):
    '''Base schema for Creator.'''
    username: Optional[str] = None
    display_name: Optional[str] = None


class CreatorCreate(CreatorBase):
    '''Schema for creating a new Creator.'''
    platform_account_id: str
    platform_id: int
    profile_pic_url: Optional[str] = None
    profile_pic_updated_at: Optional[datetime] = None
    profile_pic_asset_id: Optional[int] = None  # Optional MediaAsset ID for profile picture
    metadata_: Optional[dict[str, Any]] = None


class CreatorUpdate(BaseModel):
    '''Schema for updating a Creator.'''
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    profile_pic_updated_at: Optional[datetime] = None
    profile_pic_asset_id: Optional[int] = None  # Set profile pic to existing MediaAsset
    metadata_: Optional[dict[str, Any]] = None


class CreatorResponse(CreatorBase):
    '''Schema for Creator API responses.'''
    id: int
    profile_pic_path: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
