from redis import Redis
from rq import Queue, Retry

from app.models import Job
from app.workers import process_download_job
from app.config import settings


def get_redis_connection() -> Redis:
    '''Get a Redis connection using settings.'''
    return Redis.from_url(settings.REDIS_URL)


def get_queue(name: str = 'downloads') -> Queue:
    '''Get an RQ queue instance using settings.'''
    redis_conn = get_redis_connection()
    return Queue(name, connection=redis_conn, default_timeout=20*60)


def enqueue_job(job: Job) -> None:
    '''Enqueue a job to the queue.'''
    queue = get_queue()
    base_interval = 30  # seconds
    intervals = [base_interval * 2**i for i in range(settings.JOB_RETRIES + 1)]
    queue.enqueue(process_download_job, args=(job.id,), retry=Retry(max=settings.JOB_RETRIES, interval=intervals))
