from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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

