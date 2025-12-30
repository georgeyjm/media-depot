'''FastAPI application entry point.'''

from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.db import engine, SessionLocal, SessionDep
from app.handlers import initialize_platforms, get_handler_from_share
from app.models import Base


class DownloadRequest(BaseModel):
    '''Request schema for download endpoint.'''
    share: str


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


@app.post('/download')
async def download_from_share(request: DownloadRequest, db: SessionDep):
    '''Download media from a share URL.'''
    handler = get_handler_from_share(request.share)
    handler.load(request.share)
    post_info = handler.extract_info()
    handler.download(db=db, post_info=post_info)
