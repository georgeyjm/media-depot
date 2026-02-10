from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, desc
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import Platform, Creator, Post, PostMedia, MediaAsset, Job
from app.models.enums import JobStatus, MediaType
from app.schemas.post import PostInfo
from app.schemas.media_asset import MediaAssetCreate
from app.utils.download import download_file, hash_file


def to_relative_media_path(path: Path | str) -> str:
    '''Convert an absolute media path to a path relative to MEDIA_ROOT_DIR.'''
    path = Path(path)
    try:
        return str(path.relative_to(settings.MEDIA_ROOT_DIR))
    except ValueError:
        # Path is already relative or not under MEDIA_ROOT_DIR
        return str(path)


def to_absolute_media_path(path: Path | str) -> Path:
    '''Convert a relative media path to an absolute path under MEDIA_ROOT_DIR.'''
    path = Path(path)
    if path.is_absolute():
        return path
    if path.is_relative_to(settings.MEDIA_ROOT_DIR) and path.exists():
        # Honestly, this is kind of a hack -- a catch-all approach.
        # It is better if we can make sure whether the returns of each function is absolute or not.
        return path
    return settings.MEDIA_ROOT_DIR / path


def get_or_create_job_from_share(db: Session, share_text: str, share_url: str) -> Job:
    '''
    Create a new Job record from share text and URL.
    
    Args:
        db: Database session
        share_text: The share text containing the URL
        share_url: The extracted share URL
        
    Returns:
        Job instance
    '''
    # Check for existing active jobs (pending or processing)
    job = db.query(Job).filter(
        Job.share_url == share_url,
        Job.status.in_([JobStatus.pending, JobStatus.processing, JobStatus.completed])  # TODO: Should we allow completed jobs to be re-queued?
    ).first()
    
    if job:
        return job
    
    job = Job(
        share_text=share_text,
        share_url=share_url,
        status=JobStatus.pending,
    )
    db.add(job)
    db.commit()
    # db.refresh(job)  # Uncomment if fields like created_at are needed

    return job


def get_or_create_creator(db: Session, platform: Platform, post_info: PostInfo, download_profile_pic: bool = True, commit: bool = True) -> Creator:
    '''
    Get or create a Creator record. Currently uses PostInfo object for consistency purposes.
    
    Args:
        db: Database session
        platform: Platform instance
        post_info: db-agnostic PostInfo object containing post and creator information
        
    Returns:
        Creator instance (existing or newly created)
    '''
    creator = db.query(Creator).filter_by(
        platform_id=platform.id,
        platform_account_id=post_info.platform_account_id
    ).first()

    if creator:
        return creator
    
    # No need for Pydantic verification here because we are relying on verified Platform and PostInfo objects
    creator = Creator(
        platform_id=platform.id,
        platform_account_id=post_info.platform_account_id,
        username=post_info.username,
        display_name=post_info.display_name,
        profile_pic_asset_id=None,
        profile_pic_updated_at=None,
        profile_pic_url=None,
        metadata_=post_info.creator_metadata,
    )
    db.add(creator)
    try:
        db.flush()
    except IntegrityError:
        # Race condition: another worker created the creator between our query and insert
        # Roll back the failed insert and query again
        db.rollback()
        creator = db.query(Creator).filter_by(
            platform_id=platform.id,
            platform_account_id=post_info.platform_account_id
        ).first()
        if not creator:
            # This should never happen, but re-raise if it does
            raise

    # Process profile pic if provided
    # Download and attach is performed after the creator is created to avoid race conditions.
    if download_profile_pic and post_info.profile_pic_url:
        try:
            profile_pic_asset = download_media_asset_from_url(
                db=db,
                url=post_info.profile_pic_url,
                media_type=MediaType.profile_pic,
                filename=f'{platform.name}_{post_info.username or post_info.display_name or post_info.platform_account_id}',
            )
            creator.profile_pic_url = profile_pic_asset.url
            creator.profile_pic_asset_id = profile_pic_asset.id
            creator.profile_pic_updated_at = datetime.now(timezone.utc)
        except Exception:
            pass
    
    if commit:
        db.commit()
    return creator


def get_post_by_platform_info(db: Session, platform: Platform, post_info: PostInfo) -> Post | None:
    '''
    Get a Post record by platform and post ID.
    '''
    return db.query(Post).filter_by(
        platform_id=platform.id,
        platform_post_id=post_info.platform_post_id
    ).first()


def create_post(db: Session, platform: Platform, post_info: PostInfo, download_thumbnail: bool = True, commit: bool = True) -> Post:
    '''
    Create a Post record.
    '''
    # Should I use commit=False here? Less commits, but risk of race condition:
    # after creating the creator, we spend time downloading the thumbnail, but another worker might create the post before we commit
    creator = get_or_create_creator(db=db, platform=platform, post_info=post_info)
    post = Post(
        platform_id=platform.id,
        creator_id=creator.id,
        platform_post_id=post_info.platform_post_id,
        post_type=post_info.post_type,
        url=post_info.url,
        share_url=post_info.share_url,
        title=post_info.title,
        caption_text=post_info.caption_text,
        platform_created_at=post_info.platform_created_at,
        thumbnail_asset_id=None,
        thumbnail_url=post_info.thumbnail_url,
    )
    db.add(post)
    try:
        db.flush()
    except IntegrityError:
        # Race condition: another worker created the post between our query and insert
        # Roll back the failed insert and query again
        db.rollback()
        post = get_post_by_platform_info(db=db, platform=platform, post_info=post_info)
        if not post:
            # This should never happen, but re-raise if it does
            raise

    # Download and attach thumbnail asset if provided
    # Download and attach is performed after the post is created to avoid race conditions.
    if download_thumbnail and post_info.thumbnail_url:
        try:
            thumbnail_asset = download_media_asset_from_url(
                db=db,
                url=post_info.thumbnail_url,
                media_type=MediaType.thumbnail,
                filename=f'{platform.name}_{post_info.platform_post_id}',
            )
            post.thumbnail_asset_id = thumbnail_asset.id
        except Exception:
            pass
    
    if commit:
        db.commit()
    return post


def get_or_create_post_by_platform_info(db: Session, platform: Platform, post_info: PostInfo, commit: bool = True) -> Post:
    '''
    Get or create a Post record.
    
    Args:
        db: Database session
        platform: Platform instance
        post_info: db-agnostic PostInfo object containing post and creator information
    
    Returns:
        Post instance (existing or newly created)
    '''
    post = get_post_by_platform_info(db=db, platform=platform, post_info=post_info)
    if not post:
        post = create_post(db=db, platform=platform, post_info=post_info, commit=commit)
    
    return post


def get_or_create_media_asset(db: Session, media_asset_info: MediaAssetCreate, commit: bool = True) -> MediaAsset:
    '''
    Get or create a MediaAsset record (by filepath, or by file size and checksum).
    '''
    # Use absolute path for file operations
    absolute_path = to_absolute_media_path(media_asset_info.file_path)
    if not absolute_path.exists():
        raise FileNotFoundError(f'File not found: {absolute_path}')

    file_checksum = hash_file(absolute_path)
    file_size = absolute_path.stat().st_size

    # Use relative path for database storage and queries
    relative_path = to_relative_media_path(absolute_path)

    # Check if an entry with the same file path exists, or if an entry with the same checksum and size exists.
    media_asset = db.query(MediaAsset).filter_by(
        file_path=relative_path
    ).first() or db.query(MediaAsset).filter_by(
        checksum_sha256=file_checksum,
        file_size=file_size,
    ).first()

    if media_asset:
        return media_asset

    media_asset = MediaAsset(
        media_type=media_asset_info.media_type,
        url=media_asset_info.url,
        file_path=relative_path,
        file_format=absolute_path.suffix.lstrip('.'),
        file_size=file_size,
        checksum_sha256=file_checksum,
    )
    db.add(media_asset)
    if commit:
        db.commit()
    else:
        db.flush()

    return media_asset


def download_media_asset_from_url(
    db: Session,
    url: str,
    media_type: MediaType,
    download_dir: Optional[Path] = None,
    filename: Optional[str] = None,
    commit: bool = True,
    **kwargs: Any,
    ) -> MediaAsset:
    '''
    Download and create a MediaAsset record from a URL.
    Note the final filename may be different from the provided filename due to uniqueness constraints. Use the MediaAsset record's file_path to refer to the actual file.
    '''
    try:
        if not download_dir:
            download_dir = settings.MEDIA_ROOT_DIR / media_type.value
        filepath = download_file(url=url, download_dir=download_dir, filename=filename, **kwargs)
    except Exception as e:
        raise
    
    media_asset_info = MediaAssetCreate(
        media_type=media_type,
        url=url,
        file_path=str(filepath),
    )
    return get_or_create_media_asset(db=db, media_asset_info=media_asset_info, commit=commit)


def download_media_asset_from_urls(
    db: Session,
    urls: list[str],
    media_type: MediaType,
    download_dir: Optional[Path] = None,
    filename: Optional[str] = None,
    commit: bool = True,
    **kwargs: Any,
) -> MediaAsset:
    '''
    Download and create a single MediaAsset from a list of possible URLs.
    '''
    last_exception = None
    for url in urls:
        try:
            return download_media_asset_from_url(db=db, url=url, media_type=media_type, download_dir=download_dir, filename=filename, commit=commit, **kwargs)
        except Exception as e:
            last_exception = e
            continue
    if last_exception:
        raise last_exception


def link_post_media_asset(db: Session, post: Post, media_asset: MediaAsset, position: int = 0, commit: bool = True) -> PostMedia:
    '''
    Link a single MediaAsset record to a Post record.
    '''
    # Check for duplicate entry
    post_media = db.query(PostMedia).filter_by(
        post_id=post.id,
        media_asset_id=media_asset.id
    ).first()

    if post_media:
        return post_media
    
    post_media = PostMedia(
        post_id=post.id,
        media_asset_id=media_asset.id,
        position=position,
    )
    db.add(post_media)
    if commit:
        db.commit()
    else:
        db.flush()

    return post_media


def get_platforms(db: Session) -> list[Platform]:
    '''
    Get all Platform records.
    '''
    return db.query(Platform).all()


def get_partial_posts(
    db: Session,
    page: int = 1,
    per_page: int = 24,
    platform: Optional[str] = None,
    post_type: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[Post], int]:
    '''
    Get all Post records with pagination and filtering.
    '''    
    # Apply filters
    base_query = db.query(Post)
    if platform:
        base_query = base_query.join(Post.platform).filter(Platform.name == platform)
    if post_type:
        base_query = base_query.filter(Post.post_type == post_type)
    if search:
        # Join Creator for author search fields
        base_query = base_query.join(Post.creator)
        search_pattern = f'%{search}%'
        base_query = base_query.filter(
            or_(
                Post.title.ilike(search_pattern),
                Creator.username.ilike(search_pattern),
                Creator.display_name.ilike(search_pattern),
                Post.caption_text.ilike(search_pattern),
            )
        )
    
    # Get total count (before pagination)
    total = base_query.count()
    
    # Now add eager loading and pagination
    posts = base_query.options(
        joinedload(Post.platform),
        joinedload(Post.creator).joinedload(Creator.profile_pic),
        joinedload(Post.thumbnail),
        # joinedload(Post.media_items).joinedload(PostMedia.media_asset),
    ).order_by(desc(Post.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    return posts, total


def get_post(db: Session, post_id: int) -> Post | None:
    '''
    Get a Post record by ID.
    '''
    post = db.query(Post).options(
        joinedload(Post.platform),
        joinedload(Post.creator).joinedload(Creator.profile_pic),
        joinedload(Post.thumbnail),
        joinedload(Post.media_items).joinedload(PostMedia.media_asset),
    ).get(post_id)
    return post
