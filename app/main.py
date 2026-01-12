from typing import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.db import engine, SessionLocal
from app.models import Base
from app.routers import downloads_router, posts_router, media_router
from app.handlers import initialize_platforms


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


FRONTEND_DIR = Path(__file__).parent / 'static'
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title='Media Depot',
    description='Central depot for your favorite media content',
    version='0.1.0',
    lifespan=lifespan,
)


### Page Routes

@app.get('/')
async def root():
    '''Serve the frontend application.'''
    return FileResponse(FRONTEND_DIR / 'index.html')


@app.get('/library')
async def library():
    '''Serve the frontend application (SPA routing).'''
    return FileResponse(FRONTEND_DIR / 'index.html')


### API routes

app.include_router(downloads_router, prefix='/api')
app.include_router(posts_router, prefix='/api')

### Media route (with automatic HEIF/AVIF conversion)

app.include_router(media_router)

### Static file mounts (must be after explicit routes)

app.mount('/static', StaticFiles(directory=FRONTEND_DIR), name='static')
