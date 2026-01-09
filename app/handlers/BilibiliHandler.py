import re
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.handlers import BaseHandler
from app.db import Session
from app.models import Post, PostMedia
from app.models.enums import PostType, MediaType
from app.schemas import PostInfo, MediaAssetCreate
from app.utils.db import get_or_create_media_asset, link_post_media_asset
from app.utils.download import download_yt_dlp
from app.utils.helpers import remove_query_params, unescape_unicode


class BilibiliHandler(BaseHandler):
    '''Handler for Bilibili posts.'''
    
    PLATFORM_NAME = 'bilibili'
    PLATFORM_DISPLAY_NAME = 'BiliBili'
    FULL_URL_PATTERNS = (
        r'https?://(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]+)/?',
    )
    SHORT_URL_PATTERNS = (
        r'https?://(?:www\.)?b23\.tv/[a-zA-Z0-9]+',  # Share URL
    )
    CREATOR_URL_PATTERN = r'(?:https?:)?//space\.bilibili\.com/(\d+)'

    def __init__(self):
        super().__init__()
        self.client.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

    def extract_media_urls(self) -> list[str]:
        raise NotImplementedError
    
    def get_post_type(self) -> PostType:
        # TODO: BiliBili posts are not supported yet
        return PostType.video
    
    def extract_info(self) -> PostInfo | None:
        '''Extract post metadata and information.'''
        if not self._soup:
            self._soup = BeautifulSoup(self._html, 'html.parser')
        
        # Check if post is non-existent
        if self._soup.select_one('.error-panel > .error-msg'):
            return None
        
        # Extract video-related info
        url = remove_query_params(self._resolved_url)
        post_type = self.get_post_type()
        platform_post_id = re.match(self.FULL_URL_PATTERNS[0], self._resolved_url).group(1)
        share_url = self._current_url
        title = None
        if el := self._soup.select_one('#viewbox_report > .video-info-title h1'):
            title = el.get('title') or el.get('data-title') or el.text
        caption_text = None
        if el := self._soup.select_one('#v_desc > .basic-desc-info > span'):
            caption_text = el.text
        platform_created_at = None
        if el := self._soup.select_one('#viewbox_report > .video-info-meta .pubdate-ip-text'):
            try:
                platform_created_at = datetime.strptime(el.text, '%Y-%m-%d %H:%M:%S')
                # Bilibili datetimes are in China Standard Time (UTC+8)
                platform_created_at = platform_created_at.replace(tzinfo=ZoneInfo('Asia/Shanghai'))
            except ValueError:
                pass
        
        # Extract creator-related info
        if creator_el := self._soup.select_one('#mirror-vdcon .up-panel-container > .up-info-container'):
            # Post with single creator
            creator_name_el = creator_el.select_one('.up-detail a.up-name')
            if creator_name_el is None:
                raise ValueError('Cannot locate creator name.')
            creator_name = creator_name_el.text.strip()
            creator_url = remove_query_params(creator_name_el.get('href'))
            creator_platform_id = re.search(self.CREATOR_URL_PATTERN, creator_url).group(1)
            # profile_pic_url = creator_el.select_one('.up-avatar > .bili-avatar > img.bili-avatar-img').get('src').split('@')[0]
        else:
            # Post with multiple creators, only take the first one
            creator_el = self._soup.select_one('#mirror-vdcon .up-panel-container > .members-info-container .membersinfo-upcard')
            if creator_el is None:
                raise ValueError('Cannot find creator information.')
            creator_info_el = creator_el.select_one('.staff-info > a')
            if creator_info_el is None:
                raise ValueError('Cannot find creator information.')
            creator_name = creator_info_el.text.strip()
            creator_url = creator_el.select_one('.staff-info > a').get('href')
            creator_platform_id = re.search(self.CREATOR_URL_PATTERN, creator_url).group(1)
            # profile_pic_url = creator_el.select_one('.avatar-img > img').get('src').split('@')[0]
        profile_pic_url = re.search(r'"upData":\s*{[^}]+?"face":\s*"(.+?)"', self._html)
        if profile_pic_url is not None:
            # Convert unicode literals to actual characters
            profile_pic_url = unescape_unicode(profile_pic_url.group(1))
        thumbnail_url = re.search(r'<meta[^>]+itemprop="thumbnailUrl"[^>]+content="(.+?)"[^>]*>', self._html) or \
            re.search(r'"thumbnailUrl":\s*\[\s*"([^"]+)".*?\],', self._html)
        if thumbnail_url is not None:
            thumbnail_url = thumbnail_url.group(1)
            if thumbnail_url.startswith('//'):
                thumbnail_url = 'https:' + thumbnail_url
            if '@' in thumbnail_url:
                thumbnail_url = thumbnail_url.split('@')[0]

        return PostInfo(
            platform_post_id=platform_post_id,
            post_type=post_type,
            url=url,
            share_url=share_url,
            title=title,
            caption_text=caption_text,
            platform_created_at=platform_created_at,
            platform_account_id=creator_platform_id,
            username=creator_name,
            display_name=creator_name,
            profile_pic_url=profile_pic_url,
            thumbnail_url=thumbnail_url,
        )
    
    # TODO: This can actually be a class method, or store post so it becomes an instance method
    def download(self, db: Session, post: Post) -> list[PostMedia]:
        '''Download all media from the post.
        
        Returns:
            List of PostMedia objects.
        '''
        if post.post_type != PostType.video:
            raise NotImplementedError('Post is not a video.')

        # Check if post already has media downloaded
        # Fast path: if there's a completed job AND all files exist, skip download
        # TODO: What if job record was deleted, or media downloaded without a job?
        if post.has_completed_job() and post.all_media_exists():
            return post.media_items
        
        # TODO: Use post.url or share_url? When to add URL?
        try:
            filepath = download_yt_dlp(url=post.url, download_dir=self.DOWNLOAD_DIR)
        except Exception as e:
            raise
        media_asset_info = MediaAssetCreate(
            media_type=MediaType.video,
            url=post.url,
            file_path=str(filepath),
        )
        media_asset = get_or_create_media_asset(db=db, media_asset_info=media_asset_info)
        # TODO: Does not handle multiple media assets per post.
        post_media = link_post_media_asset(db=db, post=post, media_asset=media_asset)

        return [post_media]
