import traceback
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import SessionLocal
from app.config import settings
from app.models import Job
from app.models.enums import JobStatus
from app.handlers import get_handler_from_share
from app.utils.db import get_or_create_post_by_platform_info


def process_download_job(job_id: int) -> None:
    '''
    Process a download job.
    
    This function:
    1. Loads the job from the database
    2. Resolves the share URL and extracts post info
    3. Downloads the media
    4. Updates the job status
    
    Args:
        job_id: The ID of the job to process
    '''
    db: Session = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise ValueError(f'Job {job_id} not found')
        # Idempotency guard - allow retries if job is processing
        if job.status in (JobStatus.completed, JobStatus.failed):
            return
        
        # Mark pending jobs as processing
        if job.status == JobStatus.pending:
            job.status = JobStatus.processing
            db.commit()
        
        # Get handler from the share URL
        handler = get_handler_from_share(job.share_url)
        if handler is None:
            raise ValueError(f'No handler found for share: {job.share_text}')
        # We have to check here because initialize_platforms is not called in the worker process
        # TODO: Currently we are manually calling ensure_platform_exists, but this is not the most elegant solution
        if handler.PLATFORM is None:
            handler.__class__.ensure_platform_exists(db=db)
        
        # Load the share URL and extract info
        handler.load(job.share_url)
        post_info = handler.extract_info()
        if post_info is None:
            job.status = JobStatus.failed
            job.error = {'error': 'Post is non-existent'}
            db.commit()
            return
        
        # Get or create the post, and link job to post
        post = get_or_create_post_by_platform_info(db=db, platform=handler.PLATFORM, post_info=post_info)
        job.post_id = post.id
        db.commit()
        
        # Download the post (handler will check if already downloaded)
        post_medias = handler.download(db=db, post=post)
        job.status = JobStatus.completed
        db.commit()
        
    except Exception as e:
        # Store error for debugging and track retry attempts
        db.rollback()
        job = db.get(Job, job_id)
        if job:
            # Store error information (append to list if retrying)
            error_info = {
                'type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc(),
            }
            
            # NotImplementedError should not be retried - mark as failed immediately
            if isinstance(e, NotImplementedError):
                job.status = JobStatus.failed
                job.error = {'attempts': [error_info]}
                db.commit()
                return  # Don't retry, just return
            
            if job.error and 'attempts' in job.error:
                # Append to existing attempts
                job.error['attempts'].append(error_info)
                # Explicitly mark the field as modified since SQLAlchemy doesn't detect in-place mutations
                flag_modified(job, 'error')
            else:
                job.error = {'attempts': [error_info]}
            
            if len(job.error['attempts']) > settings.JOB_RETRIES:
                # All retries exhausted, mark as failed
                job.status = JobStatus.failed
            db.commit()
        # Always raise the exception so RQ knows to retry
        raise
    finally:
        db.close()
