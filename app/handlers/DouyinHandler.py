import re

from app.config import settings
from app.handlers import BaseHandler
from app.db import Session
from app.models import Post, PostMedia
from app.models.enums import PostType, MediaType
from app.schemas.post import PostInfo
from app.utils.db import download_media_asset_from_url, link_post_media_asset
from app.utils.helpers import remove_query_params


class DouyinHandler(BaseHandler):
    '''Handler for Douyin posts.'''
    
    PLATFORM_NAME = 'douyin'
    PLATFORM_DISPLAY_NAME = '抖音'
    FULL_URL_PATTERNS = (
        r'https?://(?:www\.)?douyin\.com/([a-zA-Z]+)/(\d+)/?',
        r'https?://(?:www\.)?iesdouyin\.com/share/([a-zA-Z]+)/(\d+)/?',
    )
    SHORT_URL_PATTERNS = (
        r'https?://v\.douyin\.com/[a-zA-Z0-9_-]+/?',  # Share URL
    )
    # CREATOR_URL_PATTERN = r'(?:https?:)?//space\.bilibili\.com/(\d+)'
    API_ROOT = f'http://localhost:{settings.DOUYIN_DOWNLOADER_PORT}'

    def extract_media_urls(self) -> list[str]:
        raise NotImplementedError
    
    def get_post_type(self) -> PostType:
        # TODO: Maybe remove
        raise NotImplementedError
    
    def extract_info(self) -> PostInfo | None:
        '''Extract post metadata and information.'''
        for pattern in self.FULL_URL_PATTERNS:
            if match := re.match(pattern, self._resolved_url):
                break
        else:
            raise ValueError(f'Cannot process Douyin URL: {self._resolved_url}')
        platform_post_type, platform_post_id = match.group(1, 2)
        
        url = remove_query_params(self._resolved_url)
        share_url = self._current_url
        post_type = {
            'video': PostType.video,
            'note': PostType.carousel,
            'slides': PostType.carousel,
        }.get(platform_post_type, PostType.unknown)

        # Use third-party API to extract post info and download links
        try:
            api_response = self.client.post(
                f'{self.API_ROOT}/douyin/detail',
                json={'detail_id': platform_post_id, 'source': True}
            )
            api_response.raise_for_status()
            api_data = api_response.json()
            if '成功' not in api_data.get('message') or not api_data.get('data'):
                return None
            api_data = api_data.get('data')
        except Exception:
            raise  # In the future, simply return None
        
        title = None
        caption_text = api_data.get('desc')
        platform_created_at = None  # TODO!!
        # re.search(r'发布时间：.*?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?</span>', self._html).group(1)

        creator_data = api_data.get('author')
        if not creator_data:
            return None  # TODO: Raise an exception maybe?
        creator_platform_id = creator_data.get('sec_uid')  # TODO: Is this preferred over uid?
        creator_username = creator_data.get('unique_id') or creator_data.get('short_id')
        creator_display_name = creator_data.get('nickname')
        if profile_pic_data := creator_data.get('avatar_thumb'):
            # TODO: This is very sketchy
            # Why not .replace('100x100', f'{width}x{height}') ??
            profile_pic_url = profile_pic_data.get('url_list')[0].replace('100x100', '1080x1080')
        else:
            profile_pic_url = None
        if video_data := api_data.get('video'):
            # Sometimes, "dynamic_cover" has higher quality, but it's cropped. Also, sometimes it's motion graphics
            if post_type == PostType.video:
                thumbnail_data = video_data.get('dynamic_cover') or video_data.get('origin_cover') or video_data.get('cover') or video_data.get('cover_original_scale')
            else:
                thumbnail_data = video_data.get('origin_cover') or video_data.get('cover') or video_data.get('cover_original_scale')
            thumbnail_url = thumbnail_data.get('url_list')[0]
        else:
            thumbnail_url = None
        creator_metadata = {
            'uid': creator_data.get('uid'),  # Purpose unknown
            'sec_uid': creator_data.get('sec_uid'),  # For user homepage URL
            'unique_id': creator_data.get('unique_id'),  # If not set, this should be the same as short_id
            'short_id': creator_data.get('short_id'),  # Supposedly, this is the more stable ID
        }

        # Store media links for download
        if post_type == PostType.video:
            self._video_data = api_data.get('video')
        elif post_type == PostType.carousel:
            self._images_data = api_data.get('images')
        elif api_data.get('images'):
            self._images_data = api_data.get('images')
        elif api_data.get('video'):
            self._video_data = api_data.get('video')
        else:
            return None

        return PostInfo(
            platform_post_id=platform_post_id,
            post_type=post_type,
            url=url,
            share_url=share_url,
            title=title,
            caption_text=caption_text,
            platform_created_at=platform_created_at,
            platform_account_id=creator_platform_id,
            username=creator_username,
            display_name=creator_display_name,
            profile_pic_url=profile_pic_url,
            thumbnail_url=thumbnail_url,
            creator_metadata=creator_metadata,
        )
    
    def download(self, db: Session, post: Post) -> list[PostMedia]:
        '''Download all media from the post.
        
        Returns:
            List of PostMedia objects.
        '''
        # Check if post already has media downloaded
        # Fast path: if there's a completed job AND all files exist, skip download
        # TODO: What if job record was deleted, or media downloaded without a job?
        # TODO: Currently, media is not downloaded but linked when a download fails even for one of the medias
        if post.has_completed_job() and post.all_media_exists():
            return post.media_items
        
        post_medias = []
        max_caption_length = 25
        if post.caption_text.startswith('#'):
            filename_prefix = f'[{post.platform_post_id}] {post.caption_text[:max_caption_length].strip()}'
        else:
            filename_prefix = f'[{post.platform_post_id}] {post.caption_text.split('#')[0][:max_caption_length].strip()}'

        if post.post_type == PostType.carousel:
            if not self._images_data:
                raise ValueError('Images data not found.')
            # TODO: What if only one file fails to download?
            for i, image_data in enumerate(self._images_data):
                # Webp images are slightly lower quality
                urls = image_data.get('url_list')
                if urls:
                    urls = list(filter(lambda url: '.webp' not in url, urls))
                    url = urls[0] if urls else image_data.get('url_list')[-1]
                else:
                    # IMPORTANT: It is possible for a live photo to only have the video part
                    url = None

                filename = f'{filename_prefix}_{i}'
                media_type = MediaType.image
                if image_data.get('clip_type') == 4 or image_data.get('video'):
                    # Live photo
                    media_type = MediaType.live_photo
                    live_video_data = image_data.get('video')
                    # Select the highest quality video source
                    # Fix this using the same algorithm down below
                    source_key = max(
                        ('play_addr', 'play_addr_h264', 'play_addr_265', 'play_addr_lowbr'),
                        key=lambda k: live_video_data.get(k, {}).get('data_size', 0),
                    )
                    live_video_url = live_video_data.get(source_key).get('url_list')[0]  # Maybe we should consider having the entire list so we can retry different URLs
                    media_asset = download_media_asset_from_url(db=db, url=live_video_url, media_type=MediaType.live_video, download_dir=self.DOWNLOAD_DIR, filename=filename, use_cookies=True)
                    post_media = link_post_media_asset(db=db, post=post, media_asset=media_asset, position=i)
                    post_medias.append(post_media)

                if not url:
                    # Skip empty URL
                    continue
                media_asset = download_media_asset_from_url(db=db, url=url, media_type=media_type, download_dir=self.DOWNLOAD_DIR, filename=filename, use_cookies=True)
                post_media = link_post_media_asset(db=db, post=post, media_asset=media_asset, position=i)
                post_medias.append(post_media)
                
        elif post.post_type == PostType.video:
            formats = self._video_data.get('bit_rate')
            max_format = max(formats, key=lambda f: f.get('bit_rate'))  # Can also use formats.get('play_addr').get('data_size'). Also, usually the first element is the highest quality
            url = max_format.get('play_addr').get('url_list')[0]  # Again, we can retry using other items in the list
            extension = max_format.get('format')
            media_asset = download_media_asset_from_url(db=db, url=url, media_type=MediaType.video, download_dir=self.DOWNLOAD_DIR, extension_fallback=extension, filename=filename_prefix, use_cookies=True)
            post_media = link_post_media_asset(db=db, post=post, media_asset=media_asset)
            post_medias.append(post_media)

        return post_medias
