from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PostMediaBase(BaseModel):
    '''Base schema for PostMedia.'''
    post_id: int
    media_asset_id: int
    position: int = 0


class PostMediaCreate(PostMediaBase):
    '''Schema for creating a PostMedia entry.'''
    pass


class PostMediaUpdate(BaseModel):
    '''Schema for updating PostMedia.'''
    position: int | None = None


class PostMediaResponse(PostMediaBase):
    '''Schema for PostMedia API responses.'''
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

