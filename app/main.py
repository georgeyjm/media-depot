from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel

from app.db import engine, SessionLocal, SessionDep
from app.models import Base, Job
from app.schemas import JobResponse
from app.handlers import initialize_platforms, extract_url_from_share
from app.utils.db import get_or_create_job_from_share
from app.utils.queue import enqueue_job


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    '''
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown events.
    '''
    # Startup: Initialize database and platforms
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        initialize_platforms(db)
    except Exception as e:
        raise
    finally:
        db.close()
    yield

    # Shutdown: Cleanup if needed
    pass


app = FastAPI(
    title='Media Depot',
    description='Central depot for your favorite media content',
    version='0.1.0',
    lifespan=lifespan,
)


@app.get('/')
async def root():
    '''Root endpoint.'''
    return {'message': 'Media Depot API'}


@app.get('/health')
async def health():
    '''Health check endpoint.'''
    from app.db import healthcheck_db
    return {'status': 'healthy' if healthcheck_db() else 'unhealthy'}


@app.post('/download', status_code=202)
async def download_from_share(share: str, db: SessionDep):
    '''
    Create a download job from a share URL and enqueue it for processing.
    Returns the job ID that can be used to track the download progress.
    '''
    # Check if share text contains a supported URL
    url = extract_url_from_share(share)
    if url is None:
        return {'error': 'Share text is from an unsupported platform'}
    
    # Create a job in the database and enqueue it for processing
    job = get_or_create_job_from_share(db=db, share_text=share, share_url=url)
    enqueue_job(job)

    return {
        'message': 'Job created and enqueued',
        'job_id': job.id,
        'status': job.status.value,
    }


@app.get('/download/{job_id}', response_model=JobResponse)
async def get_download_status(job_id: int, db: SessionDep):
    '''Get the status of a download job.'''
    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    return job
