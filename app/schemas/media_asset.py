from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import MediaType


class MediaAssetBase(BaseModel):
    '''Base schema for MediaAsset.'''
    media_type: MediaType
    file_format: Optional[str] = None
    url: Optional[str] = None
    file_size: Optional[int] = None
    file_path: str
    checksum_sha256: str


class MediaAssetCreate(MediaAssetBase):
    '''Schema for creating a new MediaAsset.'''
    pass


class MediaAssetUpdate(BaseModel):
    '''Schema for updating a MediaAsset.'''
    media_type: Optional[MediaType] = None
    file_format: Optional[str] = None
    url: Optional[str] = None
    file_size: Optional[int] = None
    file_path: Optional[str] = None
    checksum_sha256: Optional[str] = None


class MediaAssetResponse(MediaAssetBase):
    '''Schema for MediaAsset API responses.'''
    id: int
    file_path: str
    checksum_sha256: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

