import re
from datetime import datetime

from bs4 import BeautifulSoup

from app.handlers import BaseHandler
from app.models import MediaAsset
from app.models.enums import PostType, MediaType
from app.schemas.post import PostInfo


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
    
    def extract_info(self) -> PostInfo:
        '''Extract post metadata and information.'''
        if not self._soup:
            self._soup = BeautifulSoup(self._html, 'html.parser')
        
        # Extract video-related info
        url = self._resolved_url
        post_type = PostType.video  # BiliBili posts are not supported yet
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
            except ValueError:
                pass
        
        # Extract creator-related info
        creator_el = self._soup.select_one('#mirror-vdcon .up-panel-container > .members-info-container .membersinfo-upcard')
        creator_info_el = creator_el.select_one('.staff-info > a')
        creator_name = creator_info_el.text
        creator_url = creator_el.select_one('.staff-info > a').get('href')
        creator_platform_id = re.search(self.CREATOR_URL_PATTERN, creator_url).group(1)
        profile_pic_el = creator_el.select_one('.avatar-img > img')
        profile_pic_url = profile_pic_el.get('src').split('@')[0]

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
    
    def download(self) -> list[MediaAsset]:
        '''Download all media from the post.'''
        pass
    