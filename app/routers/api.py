from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import SessionDep
from app.models import Job
from app.schemas import JobResponse
from app.handlers import extract_url_from_share
from app.utils.db import get_or_create_job_from_share
from app.utils.queue import enqueue_job


router = APIRouter()


class DownloadFromShareRequest(BaseModel):
    share: str


@router.post('/download', status_code=202)
async def download_from_share(req: DownloadFromShareRequest, db: SessionDep):
    '''
    Create a download job from a share URL and enqueue it for processing.
    Returns the job ID that can be used to track the download progress.
    '''
    # Check if share text contains a supported URL
    url = extract_url_from_share(req.share)
    if url is None:
        return {'error': 'Share text is from an unsupported platform'}
    
    # Create a job in the database and enqueue it for processing
    job = get_or_create_job_from_share(db=db, share_text=req.share, share_url=url)
    enqueue_job(job)

    return {
        'message': 'Job created and enqueued',
        'job_id': job.id,
        'status': job.status.value,
    }


@router.get('/download/{job_id}', response_model=JobResponse)
async def get_download_status(job_id: int, db: SessionDep):
    '''Get the status of a download job.'''
    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    return job
