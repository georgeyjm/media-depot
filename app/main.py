'''FastAPI application entry point.'''

from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import engine, SessionLocal
from app.handlers import initialize_platforms
from app.models import Base


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
