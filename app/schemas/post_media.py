from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import MediaType


class PostMediaBase(BaseModel):
    '''Base schema for PostMedia.'''
    position: int = 0


class PostMediaCreate(PostMediaBase):
    '''Schema for creating a PostMedia entry.'''
    post_id: int
    media_asset_id: int


class PostMediaUpdate(BaseModel):
    '''Schema for updating PostMedia.'''
    position: int | None = None


class PostMediaResponse(PostMediaBase):
    '''Schema for PostMedia API responses.'''
    # We are (un-)abstracting away the MediaAsset layer here
    media_type: MediaType
    file_path: str
    # media_asset: MediaAssetResponse
    # id: int
    # created_at: datetime

    model_config = ConfigDict(from_attributes=True)
