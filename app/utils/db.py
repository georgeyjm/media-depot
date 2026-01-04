from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Platform, Creator, Post, PostMedia, MediaAsset, Job
from app.models.enums import JobStatus, MediaType
from app.schemas.post import PostInfo
from app.schemas.media_asset import MediaAssetCreate
from app.utils.download import download_file, hash_file


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
        Job.status.in_([JobStatus.pending, JobStatus.processing])
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
    db.refresh(job)

    return job


def get_or_create_creator(db: Session, platform: Platform, post_info: PostInfo, download_profile_pic: bool = True) -> Creator:
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
    
    # Download and attach profile pic asset if provided
    profile_pic_url = None
    profile_pic_asset_id = None
    profile_pic_updated_at = None
    if download_profile_pic and post_info.profile_pic_url:
        try:
            profile_pic_asset = download_media_asset_from_url(
                db=db,
                url=post_info.profile_pic_url,
                media_type=MediaType.profile_pic,
                filename=f'{platform.name}_{post_info.username}',
            )
            profile_pic_url = profile_pic_asset.url
            profile_pic_asset_id = profile_pic_asset.id
            profile_pic_updated_at = datetime.now(timezone.utc)
        except Exception:
            pass
    
    # No need for Pydantic verification here because we are relying on verified Platform and PostInfo objects
    creator = Creator(
        platform_id=platform.id,
        platform_account_id=post_info.platform_account_id,
        username=post_info.username,
        display_name=post_info.display_name,
        profile_pic_asset_id=profile_pic_asset_id,
        profile_pic_updated_at=profile_pic_updated_at,
        profile_pic_url=profile_pic_url,
    )
    db.add(creator)
    db.flush()

    return creator


def get_post(db: Session, platform: Platform, post_info: PostInfo) -> Post | None:
    '''
    Get a Post record by platform and post ID.
    '''
    return db.query(Post).filter_by(
        platform_id=platform.id,
        platform_post_id=post_info.platform_post_id
    ).first()


def create_post(db: Session, platform: Platform, post_info: PostInfo, download_thumbnail: bool = True) -> Post:
    '''
    Create a Post record.
    '''
    creator = get_or_create_creator(db=db, platform=platform, post_info=post_info)

    # Download and attach thumbnail asset if provided
    thumbnail_asset_id = None
    thumbnail_url = None
    if download_thumbnail and post_info.thumbnail_url:
        try:
            thumbnail_asset = download_media_asset_from_url(
                db=db,
                url=post_info.thumbnail_url,
                media_type=MediaType.thumbnail,
                filename=f'{platform.name}_{post_info.platform_post_id}',
            )
            thumbnail_asset_id = thumbnail_asset.id
            thumbnail_url = thumbnail_asset.url
        except Exception:
            pass
    
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
        thumbnail_asset_id=thumbnail_asset_id,
        thumbnail_url=thumbnail_url,
    )
    db.add(post)
    db.flush()
    return post


def get_or_create_post(db: Session, platform: Platform, post_info: PostInfo) -> Post:
    '''
    Get or create a Post record.
    
    Args:
        db: Database session
        platform: Platform instance
        post_info: db-agnostic PostInfo object containing post and creator information
    
    Returns:
        Post instance (existing or newly created)
    '''
    post = get_post(db=db, platform=platform, post_info=post_info)
    if not post:
        post = create_post(db=db, platform=platform, post_info=post_info)
    
    return post


def get_or_create_media_asset(db: Session, media_asset_info: MediaAssetCreate) -> MediaAsset:
    '''
    Get or create a MediaAsset record (by file size and checksum).
    '''
    if media_asset_info.file_size is None:
        media_asset = db.query(MediaAsset).filter_by(
            checksum_sha256=media_asset_info.checksum_sha256
        ).first()
    else:
        media_asset = db.query(MediaAsset).filter_by(
            checksum_sha256=media_asset_info.checksum_sha256,
            file_size=media_asset_info.file_size,
        ).first()
    
    if media_asset:
        return media_asset
    
    media_asset = MediaAsset(
        media_type=media_asset_info.media_type,
        file_format=media_asset_info.file_format,
        url=media_asset_info.url,
        file_size=media_asset_info.file_size,
        file_path=media_asset_info.file_path,
        checksum_sha256=media_asset_info.checksum_sha256,
    )
    db.add(media_asset)
    db.flush()

    return media_asset


def download_media_asset_from_url(db: Session, url: str, media_type: MediaType, filename: Optional[str] = None) -> MediaAsset:
    '''
    Download and create a MediaAsset record from a URL.
    Note the final filename may be different from the provided filename due to uniqueness constraints. Use the MediaAsset record's file_path to refer to the actual file.
    '''
    try:
        download_dir = settings.MEDIA_ROOT_DIR / media_type.value
        filepath = download_file(url=url, download_dir=download_dir, filename=filename)
    except Exception as e:
        raise
    
    media_asset_info = MediaAssetCreate(
        media_type=media_type,
        file_format=filepath.suffix.lstrip('.'),
        url=url,
        file_size=filepath.stat().st_size,
        file_path=str(filepath),
        checksum_sha256=hash_file(filepath),
    )
    return get_or_create_media_asset(db=db, media_asset_info=media_asset_info)


def link_post_media_assets(db: Session, post: Post, media_assets: list[MediaAsset]) -> list[PostMedia]:
    '''
    Link a list of MediaAsset records to a Post record.
    '''
    # TODO: Currently post media positions are determined by the location in the list,
    # this is both not ideal and doesn't support live photos. Need to rework this.
    post_medias = []
    for i, media_asset in enumerate(media_assets):
        post_media = PostMedia(
            post_id=post.id,
            media_asset_id=media_asset.id,
            position=i,
        )
        post_medias.append(post_media)
        db.add(post_media)
    db.flush()

    return post_medias
