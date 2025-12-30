import re
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.handlers import BaseHandler
from app.db import Session
from app.models import MediaAsset
from app.models.enums import PostType, MediaType
from app.schemas.post import PostInfo
from app.schemas.media_asset import MediaAssetCreate
from app.utils.db import get_post, create_post, get_or_create_media_asset, link_post_media_assets
from app.utils.download import download_yt_dlp, hash_file
from app.utils.helpers import remove_query_params


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
    
    # def resolve_url(self, url: str) -> str:
    #     '''Resolve shortened Bilibili URLs (b23.tv) to actual post URL.'''
    #     # If it's already a full URL, return as is
    #     if re.search(r'bilibili\.com/video/', url):
    #         return url
        
    #     # Follow redirects for shortened URLs
    #     return super().resolve_url(url)

    def extract_media_urls(self) -> list[str]:
        raise NotImplementedError
    
    def get_post_type(self) -> PostType:
        # TODO: BiliBili posts are not supported yet
        return PostType.video
    
    def extract_info(self) -> PostInfo:
        '''Extract post metadata and information.'''
        if not self._soup:
            self._soup = BeautifulSoup(self._html, 'html.parser')
        
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
            creator_name = creator_name_el.text.strip()
            creator_url = remove_query_params(creator_name_el.get('href'))
            creator_platform_id = re.search(self.CREATOR_URL_PATTERN, creator_url).group(1)
            profile_pic_url = None  # creator_el.select_one('.up-avatar > .bili-avatar > img.bili-avatar-img').get('src').split('@')[0]
        else:
            # Post with multiple creators, only take the first one
            creator_el = self._soup.select_one('#mirror-vdcon .up-panel-container > .members-info-container .membersinfo-upcard')
            creator_info_el = creator_el.select_one('.staff-info > a')
            creator_name = creator_info_el.text.strip()
            creator_url = creator_el.select_one('.staff-info > a').get('href')
            creator_platform_id = re.search(self.CREATOR_URL_PATTERN, creator_url).group(1)
            profile_pic_url = creator_el.select_one('.avatar-img > img').get('src').split('@')[0]

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
        )
    
    def download(self, db: Session, post_info: PostInfo) -> list[MediaAsset]:
        '''Download all media from the post.'''
        if post_info.post_type != PostType.video:
            raise NotImplementedError('Post is not a video.')

        # If post already exists, no download is performed.
        post = get_post(db=db, platform=self.PLATFORM, post_info=post_info)
        if post:
            return post
        
        post = create_post(db=db, platform=self.PLATFORM, post_info=post_info)
        filepath = download_yt_dlp(url=post_info.url, download_dir=self.DOWNLOAD_DIR)
        media_asset_info = MediaAssetCreate(
            media_type=MediaType.video,
            file_format=filepath.suffix.lstrip('.'),
            url=post_info.url,
            file_size=filepath.stat().st_size,
            file_path=str(filepath),
            checksum_sha256=hash_file(filepath),
        )
        media_asset = get_or_create_media_asset(db=db, media_asset_info=media_asset_info)
        # TODO: Does not handle multiple media assets per post.
        post_medias = link_post_media_assets(db=db, post=post, media_assets=[media_asset])
        db.commit()

        return post_medias
