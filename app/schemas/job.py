from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobStatus
from app.schemas.platform import PlatformResponse


class JobBase(BaseModel):
    '''Base schema for Job.'''
    share_text: str
    share_url: str
    status: JobStatus
    post_id: Optional[int] = None


class JobCreate(JobBase):
    '''Schema for creating a new Job.'''
    pass


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


class JobPostSummary(BaseModel):
    '''Slim post info for job list rows.'''
    id: int
    title: Optional[str] = None
    thumbnail_path: Optional[str] = None
    platform: PlatformResponse

    model_config = ConfigDict(from_attributes=True)


class JobListItem(JobResponse):
    '''Job with nested post summary for the jobs list view.'''
    post: Optional[JobPostSummary] = None
