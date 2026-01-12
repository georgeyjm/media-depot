from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)

