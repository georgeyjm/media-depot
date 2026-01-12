from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import SessionDep
from app.schemas import PlatformResponse, PostResponse, PostDetailedResponse
from app.utils.db import get_platforms, get_partial_posts, get_post


router = APIRouter()


class PostsListResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


@router.get('/posts')
async def list_posts(
    db: SessionDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    platform: Optional[str] = None,
    post_type: Optional[str] = None,
    search: Optional[str] = None,
) -> PostsListResponse:
    '''List all downloaded posts with pagination and filtering.'''
    posts, total = get_partial_posts(db, page, per_page, platform, post_type, search)

    return PostsListResponse(
        posts=[PostResponse.model_validate(post) for post in posts],
        total=total,
        page=page,
        per_page=per_page,
        has_more=(page * per_page) < total,
    )


@router.get('/posts/{post_id}')
async def get_post_detail(post_id: int, db: SessionDep) -> PostDetailedResponse:
    '''Get detailed post information including all media.'''
    post = get_post(db, post_id)

    if not post:
        raise HTTPException(status_code=404, detail='Post not found')

    return PostDetailedResponse.model_validate(post)


@router.get('/platforms')
async def list_platforms(db: SessionDep) -> list[PlatformResponse]:
    '''List all available platforms.'''
    platforms = get_platforms(db)
    return platforms
