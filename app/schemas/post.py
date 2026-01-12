from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import PostType
from app.schemas.platform import PlatformResponse
from app.schemas.creator import CreatorResponse
from app.schemas.post_media import PostMediaResponse


class PostBase(BaseModel):
    '''Base schema for Post.'''
    post_type: PostType
    title: Optional[str] = None
    caption_text: Optional[str] = None
    platform_created_at: Optional[datetime] = None


class PostInfo(PostBase):
    '''Schema for database-agnostic extracted post metadata.'''
    platform_post_id: str
    platform_account_id: str
    url: str
    share_url: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    creator_metadata: Optional[dict[str, Any]] = None


class PostCreate(PostBase):
    '''Schema for creating a new Post.'''
    platform_id: int
    creator_id: int
    profile_pic_asset_id: Optional[int] = None
    thumbnail_asset_id: Optional[int] = None
    url: str
    share_url: Optional[str] = None


class PostUpdate(BaseModel):
    '''Schema for updating a Post.'''
    title: Optional[str] = None
    caption_text: Optional[str] = None
    share_url: Optional[str] = None
    platform_created_at: Optional[datetime] = None


class PostResponse(PostBase):
    '''Schema for Post API responses.'''
    id: int
    thumbnail_path: Optional[str] = None
    platform: PlatformResponse
    creator: CreatorResponse
    created_at: datetime
    # updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PostDetailedResponse(PostResponse):
    '''Schema for Post API responses.'''
    media_items: list[PostMediaResponse]
