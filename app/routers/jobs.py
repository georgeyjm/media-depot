from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db import SessionDep
from app.models.enums import JobStatus
from app.schemas import JobListItem
from app.utils.db import get_partial_jobs


router = APIRouter()


class JobsListResponse(BaseModel):
    jobs: list[JobListItem]
    total: int
    page: int
    per_page: int
    has_more: bool


@router.get('/jobs')
async def list_jobs(
    db: SessionDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[JobStatus] = None,
    platform: Optional[str] = None,
    search: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
) -> JobsListResponse:
    '''List all jobs with pagination and optional filtering, newest first.'''
    jobs, total = get_partial_jobs(
        db, page, per_page,
        status=status,
        platform=platform,
        search=search,
        created_after=created_after,
        created_before=created_before,
    )

    return JobsListResponse(
        jobs=[JobListItem.model_validate(job) for job in jobs],
        total=total,
        page=page,
        per_page=per_page,
        has_more=(page * per_page) < total,
    )
