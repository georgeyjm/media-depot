from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import PostType


class PostBase(BaseModel):
    '''Base schema for Post.'''
    platform_post_id: str
    post_type: PostType
    url: str
    share_url: Optional[str] = None
    title: Optional[str] = None
    caption_text: Optional[str] = None
    platform_created_at: Optional[datetime] = None


class PostInfo(PostBase):
    '''Schema for database-agnostic extracted post metadata.'''
    platform_account_id: str
    username: str
    display_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    creator_metadata: Optional[dict[str, Any]] = None


class PostCreate(PostBase):
    '''Schema for creating a new Post.'''
    platform_id: int
    creator_id: int


class PostUpdate(BaseModel):
    '''Schema for updating a Post.'''
    title: Optional[str] = None
    caption_text: Optional[str] = None
    share_url: Optional[str] = None
    platform_created_at: Optional[datetime] = None


class PostResponse(PostBase):
    '''Schema for Post API responses.'''
    id: int
    platform_id: int
    creator_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
