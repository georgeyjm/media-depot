from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobStatus


class JobBase(BaseModel):
    '''Base schema for Job.'''
    share_text: str
    status: JobStatus
    post_id: Optional[int] = None


class JobCreate(JobBase):
    '''Schema for creating a new Job.'''
    share_url: str


class JobUpdate(BaseModel):
    '''Schema for updating a Job.'''
    status: Optional[JobStatus] = None
    error: Optional[dict[str, Any]] = None


class JobResponse(JobBase):
    '''Schema for Job API responses.'''
    id: int
    created_at: datetime
    updated_at: datetime
    error: Optional[dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)
