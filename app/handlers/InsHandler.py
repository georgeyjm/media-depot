import re
from datetime import datetime
from pathlib import Path
from typing import Any

from gallery_dl import config as gdl_config
from gallery_dl.job import DataJob

from app.config import settings
from app.handlers import BaseHandler
from app.db import Session
from app.models import Post, PostMedia
from app.models.enums import PostType, MediaType
from app.schemas import PostInfo, MediaAssetCreate
from app.utils.db import get_or_create_media_asset, link_post_media_asset
from app.utils.download import download_gallery_dl, _get_cookie_file
from app.utils.helpers import sanitize_filename, remove_query_params


class InsHandler(BaseHandler):
    '''Handler for Instagram posts and reels.'''

    PLATFORM_NAME = 'ins'
    PLATFORM_DISPLAY_NAME = 'Instagram'
    FULL_URL_PATTERNS = (
        r'https?://(?:www\.)?instagram\.com/([a-z]+)/([a-zA-Z0-9_-]+)/?',  # types include "p", "reels?", "tv"
    )
    SHORT_URL_PATTERNS = (
        r'https?://(?:www\.)?instagram\.com/share/[a-zA-Z0-9_-]+/?',
    )
    USE_COOKIES = True

    def __init__(self):
        super().__init__()
        media_items: list[dict] = []
        self._configure_gallery_dl()
    
    def extract_media_urls(self) -> list[str]:
        raise NotImplementedError

    def _configure_gallery_dl(self) -> None:
        '''Configure gallery-dl with cookies and download settings.'''
        # Load default config
        gdl_config.load()

        # Set cookies from cookie file (same as yt-dlp)
        cookie_file = _get_cookie_file()
        if cookie_file:
            gdl_config.set(('extractor', 'instagram'), 'cookies', str(cookie_file))

        # Configure download directory
        gdl_config.set(('extractor',), 'base-directory', str(self.DOWNLOAD_DIR or settings.MEDIA_ROOT_DIR / 'ins'))

        # Set filename template
        gdl_config.set(('extractor', 'instagram'), 'filename', '{post_shortcode}_{num}.{extension}')

        # Configure to include metadata
        gdl_config.set(('extractor', 'instagram'), 'metadata', True)

    def get_post_type(self, post_type_string: str) -> PostType:
        '''Determine post type from metadata.'''
        # if not self._metadata:
        #     return PostType.unknown

        # Check if it's a video/reel
        # media_items = media_items
        # if len(media_items) == 1:
        #     item = media_items[0]
        #     if item.get('typename') == 'GraphVideo' or item.get('video_url'):
        #         return PostType.video
        #     return PostType.carousel  # Single image is also treated as carousel
        # elif len(media_items) > 1:
        #     return PostType.carousel

        # Fallback based on URL pattern
        if not post_type_string:
            match = re.match(self.FULL_URL_PATTERNS[0], self._resolved_url)
            post_type_string = match.group(1)
        if post_type_string in ('reel', 'reels', 'tv'):
            return PostType.video
        elif post_type_string in ('p', 'post'):
            return PostType.carousel
        return PostType.unknown

    def extract_info(self) -> PostInfo | None:
        '''Extract post metadata using gallery-dl DataJob.'''
        if not self._resolved_url:
            return None

        # Use DataJob to extract metadata without downloading
        try:
            job = DataJob(self._resolved_url, file=None)  # file=None suppresses JSON output
            job.run()
        except Exception as e:
            print(f'gallery-dl DataJob failed: {e}')
            raise e
        if not job.data:
            print('No data returned from gallery-dl')
            return None
        
        post_type_string, shortcode = re.match(self.FULL_URL_PATTERNS[0], self._resolved_url).groups()
        post_type = self.get_post_type(post_type_string)

        # Process extracted data
        # DataJob returns tuples: (message_type, url_or_path, kwdict)
        # message_type: 1 = url, 2 = url (queue), 3 = directory
        self.media_items: list[dict[str, Any]] = [item[2] for item in job.data if item[0] == 3]

        assert job.data[0][0] == 2, 'First message should be post metadata'
        post_metadata = job.data[0][1]
        if not post_metadata:
            print('Post metadata is empty')
            return None

        for item in job.data:
            msg_type = item[0]
            # if msg_type == 3:  # Directory message: (msg_type, path, kwdict)
            #     post_metadata = item[2]
            if msg_type == 1:  # URL message: (msg_type, url, kwdict)
                print('Encountered unexcepted message with type 1:')
                print(item)

        # Post info
        share_url = self._current_url
        platform_post_id = post_metadata.get('post_shortcode') or post_metadata.get('shortcode') or shortcode
        url = post_metadata.get('post_url') or remove_query_params(self._resolved_url)
        caption_text = post_metadata.get('description') or None
        platform_created_at = None
        if post_date := post_metadata.get('date') or post_metadata.get('post_date'):
            if isinstance(post_date, str):
                platform_created_at = datetime.strptime(post_date, '%Y-%m-%d %H:%M:%S')
            elif isinstance(post_date, (int, float)):
                platform_created_at = datetime.fromtimestamp(post_date)
            elif isinstance(post_date, datetime):
                platform_created_at = post_date
        
        # Thumbnail URL
        thumbnail_url = None
        if self.media_items:
            first_item = self.media_items[0]
            thumbnail_url = first_item.get('display_url') or first_item.get('thumbnail_url')

        # Creator info
        user_data = post_metadata.get('owner', {}) or post_metadata.get('user', {})
        creator_platform_id = post_metadata.get('owner_id') or user_data.get('id') or user_data.get('pk')
        creator_username = post_metadata.get('username') or user_data.get('username')
        creator_display_name = post_metadata.get('fullname') or user_data.get('full_name')

        # Creator profile pic
        profile_pic_url = user_data.get('profile_pic_url_hd')
        if not profile_pic_url:
            profile_pic_info = user_data.get('hd_profile_pic_url_info') or user_data.get('profile_pic_url_info') or {}
            profile_pic_url = profile_pic_info.get('url')
        if not profile_pic_url:
            profile_pic_url = user_data.get('profile_pic_url')
        if not profile_pic_url:
            # Manually request another job for profile pic
            avatar_url = f'https://www.instagram.com/{creator_username}/avatar'
            job = DataJob(avatar_url, file=None)
            job.run()
            for data in job.data[::-1]:
                data = data[-1]
                if (user_data := data.get('user')) or (user_data := data.get('owner')):
                    profile_pic_url = user_data.get('profile_pic_url_hd') or user_data.get('profile_pic_url')
                    break

        return PostInfo(
            platform_post_id=platform_post_id,
            post_type=post_type,
            url=url,    
            share_url=share_url,
            title=None,  # Instagram doesn't have titles
            caption_text=caption_text,
            platform_created_at=platform_created_at,
            platform_account_id=creator_platform_id,
            username=creator_username,
            display_name=creator_display_name,
            profile_pic_url=profile_pic_url,
            thumbnail_url=thumbnail_url,
        )

    def download(self, db: Session, post: Post) -> list[PostMedia]:
        '''Download all media from the post using gallery-dl.

        Returns:
            List of PostMedia objects.
        '''
        # Check if post already has media downloaded
        if post.has_completed_job() and post.all_media_exists():
            return post.media_items

        if not self._resolved_url:
            raise ValueError('No resolved URL available for download')

        post_medias = []

        # Build filename template
        max_caption_length = 25
        caption_preview = (post.caption_text or '').strip()[:max_caption_length]
        if caption_preview.startswith('#'):
            filename_prefix = f'[{post.platform_post_id}] {caption_preview}'
        else:
            filename_prefix = f'[{post.platform_post_id}] {caption_preview.split('#')[0].strip()}'
        filename_prefix = sanitize_filename(filename_prefix)
        filename_template = f'{filename_prefix}_{{num}}.{{extension}}'

        # Download using gallery-dl
        downloaded_files = download_gallery_dl(
            url=self._resolved_url,
            download_dir=self.DOWNLOAD_DIR,
            filename=filename_template,
            extractor='instagram',
            extra_options={'skip': False},  # Forcing redownload so the below assertion can match (a very hacky & inefficient workaround)
        )
        assert len(downloaded_files) == len(self.media_items), f'Mismatched lengths of downloaded files ({len(downloaded_files)}) with media items ({len(self.media_items)})'

        # Sort by filename to maintain order
        # Actually, we assume it is in order, mostly to avoid misordered issues caused by same checksum as thumbnails
        # downloaded_files.sort(key=lambda p: p.name)

        # Create MediaAsset and PostMedia records for each downloaded file
        for i, file_path in enumerate(downloaded_files):
            # Determine media type from extension
            ext = file_path.suffix.lower()
            if ext in ('.mp4', '.mov', '.webm', '.mkv', '.avi'):
                media_type = MediaType.video
            elif ext in ('.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.gif'):
                media_type = MediaType.image
            else:
                media_type = MediaType.image  # Default to image

            # Create or get MediaAsset
            # Note we are taking the media URL from the earlier DataJob
            # We need to assume that the two jobs give matching media files
            if media_type == MediaType.video:
                asset_url = self.media_items[i].get('video_url')
            else:
                asset_url = self.media_items[i].get('display_url')
            media_asset_info = MediaAssetCreate(
                media_type=media_type,
                url=asset_url,
                file_path=str(file_path),
            )
            media_asset = get_or_create_media_asset(db=db, media_asset_info=media_asset_info)

            # Link to post
            post_media = link_post_media_asset(
                db=db,
                post=post,
                media_asset=media_asset,
                position=i,
            )
            post_medias.append(post_media)

        return post_medias
