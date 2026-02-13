from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import selectinload

from app.db import SessionDep
from app.models import Post, PostMedia
from app.schemas import PlatformResponse, PostResponse, PostDetailedResponse
from app.utils.db import get_platforms, get_partial_posts, get_post, delete_orphaned_media_files


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


@router.delete('/posts/{post_id}', status_code=200)
async def delete_post(post_id: int, db: SessionDep) -> dict:
    '''Delete a post and all its media items.

    Cascade deletes:
    - Post record
    - All PostMedia records (via cascade='all, delete-orphan')
    - All Job records associated with the post
    - Thumbnail MediaAsset if orphaned

    Also deletes physical files from disk if no other posts reference them.
    '''
    post = db.query(Post).options(
        selectinload(Post.media_items).selectinload(PostMedia.media_asset),
        selectinload(Post.thumbnail)
    ).filter_by(id=post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail='Post not found')

    # Collect MediaAssets for potential file deletion
    media_assets_to_check = []
    for post_media in post.media_items:
        media_assets_to_check.append(post_media.media_asset)
    if post.thumbnail:
        media_assets_to_check.append(post.thumbnail)

    # Delete post (cascades to PostMedia and Jobs)
    db.delete(post)
    db.commit()

    # Check and delete orphaned media files
    deleted_files = delete_orphaned_media_files(db, media_assets_to_check)

    return {
        'message': 'Post deleted successfully',
        'post_id': post_id,
        'files_deleted': deleted_files
    }


@router.delete('/posts/{post_id}/media/{post_media_id}', status_code=200)
async def delete_post_media(post_id: int, post_media_id: int, db: SessionDep) -> dict:
    '''Delete a specific media item from a post.

    Deletes:
    - PostMedia record linking post to media asset
    - Physical file if no other posts reference the same asset

    Does NOT delete:
    - The Post itself (even if it becomes empty)
    - MediaAsset record (stays in DB even if orphaned for safety)
    '''
    post_media = db.query(PostMedia).options(
        selectinload(PostMedia.media_asset),
        selectinload(PostMedia.post)
    ).filter_by(id=post_media_id, post_id=post_id).first()

    if not post_media:
        raise HTTPException(status_code=404, detail='Post media not found')

    # Store media asset for later file deletion check
    media_asset = post_media.media_asset

    # Delete PostMedia record
    db.delete(post_media)
    db.commit()

    # Check and delete orphaned media file
    deleted_files = delete_orphaned_media_files(db, [media_asset])

    # Reorder remaining media items
    remaining_items = db.query(PostMedia).filter_by(post_id=post_id).order_by(PostMedia.position).all()
    # for idx, item in enumerate(remaining_items):
    #     item.position = idx
    # db.commit()

    return {
        'message': 'Media item deleted successfully',
        'post_media_id': post_media_id,
        'files_deleted': deleted_files,
        'remaining_count': len(remaining_items)
    }
