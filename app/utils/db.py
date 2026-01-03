from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Platform, Creator, Post, PostMedia, MediaAsset, Job
from app.models.enums import JobStatus
from app.schemas.post import PostInfo
from app.schemas.media_asset import MediaAssetCreate


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


def get_or_create_creator(db: Session, platform: Platform, post_info: PostInfo) -> Creator:
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
    
    if not creator:
        # No need for Pydantic verification here because we are relying on verified Platform and PostInfo objects
        creator = Creator(
            platform_id=platform.id,
            platform_account_id=post_info.platform_account_id,
            username=post_info.username,
            display_name=post_info.display_name,
            profile_pic_url=post_info.profile_pic_url,
            profile_pic_updated_at=datetime.now(timezone.utc),
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


def create_post(db: Session, platform: Platform, post_info: PostInfo) -> Post:
    '''
    Create a Post record.
    '''
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
            file_size=media_asset_info.file_size,
            checksum_sha256=media_asset_info.checksum_sha256
        ).first()

    if not media_asset:
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
