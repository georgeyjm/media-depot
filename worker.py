#!/usr/bin/env python3
'''
Standalone worker script for processing download jobs.

This script starts an RQ worker that consumes jobs from the 'downloads' queue.
Run this script to process background download jobs.

Usage:
    python worker.py
    # or
    rq worker downloads
    # For macOS, due to Objective-C runtime issues, we need to use SimpleWorker instead:
    rq worker downloads --worker-class rq.worker.SimpleWorker --logging_level DEBUG
    # or set the following environment variable:
    OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
'''

import sys

from rq import Worker

from app.db import SessionLocal
from app.handlers import initialize_platforms
from app.utils.queue import get_redis_connection, get_queue


def main():
    '''Start the RQ worker.'''
    # Seed the platform rows and populate each handler class's PLATFORM /
    # DOWNLOAD_DIR class variables. Jobs run in forked children, which inherit
    # this class state, so doing it once here covers every job.
    db = SessionLocal()
    try:
        initialize_platforms(db)
    finally:
        db.close()

    redis_conn = get_redis_connection()
    queue = get_queue()
    worker = Worker([queue], connection=redis_conn)

    print(f'Starting worker for queue: {queue.name}')
    print('Press Ctrl+C to stop the worker')
    try:
        # with_scheduler is required for Retry(interval=...) to work: retries
        # land in the ScheduledJobRegistry and only the scheduler re-enqueues them
        worker.work(with_scheduler=True)
    except KeyboardInterrupt:
        print('\nWorker stopped by user')
        sys.exit(0)


if __name__ == '__main__':
    main()

