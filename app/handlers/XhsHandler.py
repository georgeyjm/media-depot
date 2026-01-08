import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.config import settings
from app.handlers import BaseHandler
from app.db import Session
from app.models import Post, PostMedia
from app.models.enums import PostType, MediaType
from app.schemas.post import PostInfo
from app.utils.db import download_media_asset_from_url, link_post_media_asset
from app.utils.helpers import remove_query_params


class XhsHandler(BaseHandler):
    '''Handler for Xiaohongshu posts.'''
    
    PLATFORM_NAME = 'xhs'
    PLATFORM_DISPLAY_NAME = '小红书'
    FULL_URL_PATTERNS = (
        r'https?://(?:www\.)?xiaohongshu\.com/([a-zA-Z]+)/(?:[a-zA-Z]+/)?([a-zA-Z0-9]+)/?\??',
    )
    SHORT_URL_PATTERNS = (
        r'https?://xhslink\.com/[a-zA-Z]/[a-zA-Z0-9]+/?',  # Share URL
    )
    # CREATOR_URL_PATTERN = r'(?:https?:)?//space\.bilibili\.com/(\d+)'
    API_ROOT = f'http://localhost:{settings.XHS_DOWNLOADER_PORT}'

    def extract_media_urls(self, post_type: PostType) -> list[str]:
        if post_type == PostType.video:
            match = re.search(r'"consumer":\s*{.*?"originVideoKey":\s*"(.+?)"\s*}', self._html)
            if match:
                url = 'https://sns-video-bd.xhscdn.com/' + match.group(1).encode('utf-8').decode('unicode-escape')
                return [url]
            print(f'Origin video URL not found in HTML: {self._html}')
        else:
            return []
    
    def get_post_type(self) -> PostType:
        # TODO: Maybe remove
        raise NotImplementedError
    
    def extract_info(self) -> PostInfo | None:
        '''Extract post metadata and information.'''
        
        # TODO: Check if post is non-existent
        
        # platform_post_type, platform_post_id = re.match(self.FULL_URL_PATTERNS[0], self._resolved_url).group(1, 2)
        # url = remove_query_params(self._resolved_url)
        # share_url = self._current_url
        # post_type = {
        #     'video': PostType.video,
        #     'note': PostType.carousel,
        # }.get(platform_post_type, PostType.unknown)

        # Use third-party API to extract post info and download links
        try:
            api_response = self.client.post(
                f'{self.API_ROOT}/xhs/detail',
                json={'url': self._resolved_url}
            )
            api_response.raise_for_status()
            api_data = api_response.json()
            if '成功' not in api_data.get('message') or not api_data.get('data'):
                return None
            api_data = api_data.get('data')
        except Exception:
            raise  # In the future, simply return None
        
        post_type = {
            '图集': PostType.carousel,
            '图文': PostType.carousel,
            '视频': PostType.video,
        }.get(api_data.get('作品类型'), PostType.unknown)
        platform_post_id = api_data.get('作品ID')

        url = self._resolved_url # We retain xsec_token, unlike: api_data.get('作品链接')
        title = api_data.get('作品标题')
        caption_text = api_data.get('作品描述')
        platform_created_at = datetime.strptime(api_data.get('发布时间'), '%Y-%m-%d_%H:%M:%S')
        platform_created_at = platform_created_at.astimezone()  # XHS returns time in local timezone

        creator_platform_id = api_data.get('作者ID')
        creator_url = api_data.get('作者链接')
        creator_username = None  # TODO: It's actually surprisingly hard to get this - need to bypass auth and request the user homepage
        creator_display_name = api_data.get('作者昵称')
        profile_pic_url = re.search(r'"user":\s*?{.*?"avatar":\s*"(.+?)"', self._html)
        
        if profile_pic_url is not None:
            # Convert unicode literals to actual characters
            profile_pic_url = profile_pic_url.group(1).encode('utf-8').decode('unicode-escape')
        if post_type == PostType.video:
            thumbnail_file_id = re.search(r'"imageList":.*?"fileId":\s*"(.+?)"', self._html) or \
                re.search(r'"video":.*?"image":.*?"firstFrameFileid":\s*"(.+?)"', self._html)
            if thumbnail_file_id is not None:
                thumbnail_url = 'https://ci.xiaohongshu.com/' + thumbnail_file_id.group(1).encode('utf-8').decode('unicode-escape')
            elif thumbnail_url := re.search(r'"imageList":.*?(?:(?:"infoList":\s*\[.+?\].*?"url":\s*"(.+?)")|(?:"url":\s*"(.+?)".*?"infoList":\s*\[.+?\]))', self._html):
                thumbnail_url = thumbnail_url.group(1) or thumbnail_url.group(2)
                thumbnail_url = thumbnail_url.encode('utf-8').decode('unicode-escape')
            else:
                thumbnail_url = None
        else:
            thumbnail_url = re.search(r'"imageList":\s*?\[{.*?"urlDefault":\s*"(.+?)"', self._html)
            if thumbnail_url is not None:
                thumbnail_url = thumbnail_url.group(1).encode('utf-8').decode('unicode-escape')
        
        # Store media links for download
        if post_type == PostType.video:
            video_url = self.extract_media_urls(post_type)
            if not video_url:
                raise ValueError('Origin video URL not found')
            self._video_url = video_url[0]
        elif post_type == PostType.carousel:
            self._images_data = api_data.get('下载地址'), api_data.get('动图地址')
        else:
            return None

        return PostInfo(
            platform_post_id=platform_post_id,
            post_type=post_type,
            url=url,
            share_url=self._current_url,
            title=title,
            caption_text=caption_text,
            platform_created_at=platform_created_at,
            platform_account_id=creator_platform_id,
            username=creator_username,
            display_name=creator_display_name,
            profile_pic_url=profile_pic_url,
            thumbnail_url=thumbnail_url,
        )
    
    def download(self, db: Session, post: Post) -> list[PostMedia]:
        '''Download all media from the post.
        
        Returns:
            List of PostMedia objects.
        '''
        # Check if post already has media downloaded
        # Fast path: if there's a completed job AND all files exist, skip download
        # TODO: What if job record was deleted, or media downloaded without a job?
        if post.has_completed_job() and post.all_media_exists():
            return post.media_items
        
        post_medias = []
        max_caption_length = 25
        filename_prefix = f'[{post.platform_post_id}] {post.title[:max_caption_length].strip()}'

        if post.post_type == PostType.video:
            media_asset = download_media_asset_from_url(
                db=db,
                url=self._video_url,
                media_type=MediaType.video,
                download_dir=self.DOWNLOAD_DIR,
                filename=filename_prefix
            )
            post_media = link_post_media_asset(db=db, post=post, media_asset=media_asset)
            post_medias.append(post_media)

        elif post.post_type == PostType.carousel:
            images, videos = self._images_data
            assert len(images) == len(videos), 'Image list and video list must have the same length.'
            for i, (image_url, video_url) in enumerate (zip(images, videos)):
                filename = f'{filename_prefix}_{i}'
                media_type = MediaType.image
                if video_url:
                    # Live photo's video part
                    media_type = MediaType.live_photo
                    media_asset = download_media_asset_from_url(
                        db=db,
                        url=video_url,
                        media_type=MediaType.live_video,
                        download_dir=self.DOWNLOAD_DIR,
                        filename=filename,
                        chunk_size=1024 * 1024 * 8
                    )
                    post_media = link_post_media_asset(db=db, post=post, media_asset=media_asset, position=i)
                    post_medias.append(post_media)
                
                # Download the photo
                image_url = image_url.replace('/format/png', '/format/auto')
                media_asset = download_media_asset_from_url(db=db, url=image_url, media_type=media_type, download_dir=self.DOWNLOAD_DIR, filename=filename)
                post_media = link_post_media_asset(db=db, post=post, media_asset=media_asset, position=i)
                post_medias.append(post_media)

        return post_medias
