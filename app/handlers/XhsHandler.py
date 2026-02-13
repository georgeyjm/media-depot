import re
import json
from datetime import datetime

from bs4 import BeautifulSoup

from app.config import settings
from app.handlers import BaseHandler
from app.db import Session
from app.models import Post, PostMedia
from app.models.enums import PostType, MediaType
from app.schemas.post import PostInfo
from app.utils.db import download_media_asset_from_url, link_post_media_asset
from app.utils.helpers import remove_query_params, unescape_unicode


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
    USE_COOKIES = True
    API_ROOT = f'http://localhost:{settings.XHS_DOWNLOADER_PORT}'
    XHS_PHOTO_ROOT = 'https://ci.xiaohongshu.com/'
    XHS_VIDEO_ROOT = 'https://sns-video-bd.xhscdn.com/'

    def extract_media_urls(self, post_type: PostType) -> list[str]:
        assert self._html is not None, 'Page is not loaded yet'
        if post_type == PostType.video:
            match = re.search(r'"consumer":\s*{.*?"originVideoKey":\s*"(.+?)"\s*}', self._html)
            if not match:
                raise ValueError(f'Origin video URL not found in HTML: {self._html}')
            if match:
                url = self.XHS_VIDEO_ROOT + unescape_unicode(match.group(1))
                return [url]
            print(f'Origin video URL not found in HTML: {self._html}')
        return []

    def extract_media_urls_non_origin(self, post_type: PostType, note_data: dict) -> list[str]:
        '''
        Since Xiaohongshu removed "originVideoKey" for videos, we only have access to non-original compressed videos.
        This function extracts those video links.
        '''
        assert self._html is not None, 'Page is not loaded yet'
        if post_type == PostType.video:
            assert 'video' in note_data and 'media' in note_data['video'], f'Missing video keys in note data: {note_data}'
            media_data = note_data['video']['media']
            url = unescape_unicode(self._get_max_quality_video_url(media_data))
            return [url]
        return []
    
    def _get_max_quality_video_url(self, media_data: dict) -> str:
        stream_data = media_data.get('stream')
        if not stream_data:
            raise ValueError(f'No stream data found in {media_data}')
        
        encoding_priority = ('h265', 'h266', 'av1', 'h264')
        for enc in encoding_priority:
            if streams := stream_data.get(enc):
                break
        else:
            raise ValueError('Cannot find any valid encoding')
        
        stream = max(streams, key=lambda s: s.get('videoBitrate', 0))  # Alternative: 'avgBitrate', 'height'/'width'
        # In the future, we can return all URLs for fallback purposes
        url = stream.get('masterUrl') or stream.get('backupUrls', [])[0]
        if not url:
            raise ValueError(f'Cannot find a valid URL in {stream}')
        return url
    
    def get_post_type(self, post_type_string: str) -> PostType:
        return {
            # Web values:
            'normal': PostType.carousel,
            'video': PostType.video,
            # API values:
            '图集': PostType.carousel,
            '图文': PostType.carousel,
            '视频': PostType.video,
        }.get(post_type_string.lower(), PostType.unknown)
    
    def extract_info_by_api(self) -> PostInfo | None:
        '''Extract post metadata and information using third-party API.'''
        assert self._resolved_url is not None and self._html is not None, 'Page is not loaded yet'
        
        try:
            api_response = self.client.post(
                f'{self.API_ROOT}/xhs/detail',
                json={'url': self._resolved_url, 'cookie': ''}
            )
            api_response.raise_for_status()
            api_data = api_response.json()
            if '成功' not in api_data.get('message') or not api_data.get('data'):
                if 'xiaohongshu.com/404/' in self._resolved_url:
                    # Post is non-existent
                    return None
                print(f'XHS API did not return valid data: {api_data}')
                raise ValueError(f'XHS API did not return valid data')
            api_data = api_data.get('data')
        except Exception:
            raise  # In the future, simply return None
        
        post_type = self.get_post_type(api_data.get('作品类型'))
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
            profile_pic_url = remove_query_params(unescape_unicode(profile_pic_url.group(1)))
        if post_type == PostType.video:
            thumbnail_file_id = re.search(r'"imageList":.*?"fileId":\s*"(.+?)"', self._html) or \
                re.search(r'"video":.*?"image":.*?"firstFrameFileid":\s*"(.+?)"', self._html)
            if thumbnail_file_id is not None:
                thumbnail_url = self.XHS_PHOTO_ROOT + unescape_unicode(thumbnail_file_id.group(1))
            elif thumbnail_url := re.search(r'"imageList":.*?(?:(?:"infoList":\s*\[.+?\].*?"url":\s*"(.+?)")|(?:"url":\s*"(.+?)".*?"infoList":\s*\[.+?\]))', self._html):
                thumbnail_url = thumbnail_url.group(1) or thumbnail_url.group(2)
                thumbnail_url = unescape_unicode(thumbnail_url)
            else:
                thumbnail_url = None
        else:
            thumbnail_url = re.search(r'"imageList":\s*?\[{.*?"urlDefault":\s*"(.+?)"', self._html)
            if thumbnail_url is not None:
                thumbnail_url = unescape_unicode(thumbnail_url.group(1))
        
        # Store media links for download
        if post_type == PostType.video:
            video_url = self.extract_media_urls(post_type)
            if not video_url:
                raise ValueError('Origin video URL not found')
            self._video_url = video_url[0]
        elif post_type == PostType.carousel:
            self._images_data = api_data.get('下载地址'), api_data.get('动图地址')
        else:
            print('Unsupported post type:', post_type)
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
    
    def extract_info(self) -> PostInfo | None:
        '''Extract post metadata and information.'''

        # Try using third-party API to extract post info and download links
        # try:
        #     return self.extract_info_by_api()
        # except Exception as e:
        #     print('Failed to extract info by API:', e)
        #     pass
        
        assert self._resolved_url is not None and self._html is not None, 'Page is not loaded yet'

        if 'xiaohongshu.com/404/' in self._resolved_url:
            # This doesn't actually mean the post is non-existent,
            # but Xhs does not allow web access to these posts
            # TODO: Need to find a workaround, or at least mark it.
            return None
        if self._resolved_url.endswith('xiaohongshu.com') or self._resolved_url.endswith('xiaohongshu.com/explore'):
            # Post is non-existent
            return None
        
        if self._soup is None:
            self._soup = BeautifulSoup(self._html, 'html.parser')
        if el := self._soup.find('script', string=re.compile(r'window\.__INITIAL_STATE__=')):  # type: ignore
            # Parse JavaScript data
            js_string = el.string[len('window.__INITIAL_STATE__='):]
            js_string = re.sub(r'\bundefined\b', 'null', js_string)
            js_string = re.sub(r'\bNaN\b|\bInfinity\b', 'null', js_string)
            try:
                note_data = json.loads(js_string)
                if 'noteData' in note_data:
                    # Using iOS Safari user agent
                    note_data = note_data['noteData']['data']['noteData']
                else:
                    # Using Web Chrome user agent
                    note_data = list(note_data['note']['noteDetailMap'].values())[0]['note']
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(self._resolved_url)
                print(js_string)
                raise ValueError('Failed to parse JavaScript data') from e
        else:
            raise ValueError('Failed to find JavaScript data')
        
        metadata = {}
        post_type = self.get_post_type(note_data.get('type'))

        url = self._resolved_url  # We retain xsec_token, unlike: api_data.get('作品链接')
        platform_post_id = note_data.get('noteId')
        title = note_data.get('title')
        caption_text = note_data.get('desc')
        if caption_text:
            # Reformat #[话题]# tags
            caption_text = re.sub(r'(#[^#]+)\[话题\]#', r'\1 ', caption_text)
        platform_created_at = note_data.get('time') or note_data.get('lastUpdateTime')
        if platform_created_at:
            platform_created_at = datetime.fromtimestamp(platform_created_at / 1000)
            platform_created_at = platform_created_at.astimezone()  # XHS returns time in local timezone

        if not (user_data := note_data.get('user')):
            raise ValueError('User data not found')
        creator_platform_id = user_data.get('userId')
        creator_username = None  # TODO: It's actually surprisingly hard to get this - need to bypass auth and request the user homepage
        creator_display_name = user_data.get('nickName')
        profile_pic_url = None
        if avatar_full_url := user_data.get('avatar'):
            profile_pic_url = remove_query_params(avatar_full_url)
        thumbnail_url = None
        if file_id := note_data.get('cover', {}).get('fileId') or note_data.get('imageList', [{}])[0].get('fileId'):
            thumbnail_url = self.XHS_PHOTO_ROOT + file_id  # No need to unescape_unicode since JSON is already decoded
        elif post_type == PostType.video:
            file_id = note_data.get('video', {}).get('image', {}).get('firstFrameFileid')
            thumbnail_url = self.XHS_PHOTO_ROOT + file_id

        # Extract media links for download
        if post_type == PostType.video:
            try:
                video_url = self.extract_media_urls(post_type)
                if not video_url:
                    raise ValueError('Origin video URL not found')
            except Exception as e:
                metadata['using_non_origin_video'] = True
                video_url = self.extract_media_urls_non_origin(post_type, note_data)
            if not video_url:
                raise ValueError('Video URL not found')
            self._video_url = video_url[0]
        elif post_type == PostType.carousel:
            self._images_data = [], []  # images, (live) videos
            images_data = note_data.get('imageList')
            if not images_data:
                raise ValueError('Image list not found')
            for image_data in images_data:
                file_id = image_data.get('fileId')
                if not file_id:
                    print('Image file ID not found', image_data)
                    continue
                image_url = self.XHS_PHOTO_ROOT + file_id
                self._images_data[0].append(image_url)

                if not image_data.get('livePhoto'):
                    self._images_data[1].append(None)
                else:
                    video_url = self._get_max_quality_video_url(image_data)
                    self._images_data[1].append(video_url)
        
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
            metadata=metadata,
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
        title = post.title or post.caption_text or ''
        filename_prefix = f'[{post.platform_post_id}] {title[:max_caption_length].strip()}'

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
                # Can technically apply remove_query_params here
                image_url = image_url.replace('/format/png', '/format/auto')
                media_asset = download_media_asset_from_url(db=db, url=image_url, media_type=media_type, download_dir=self.DOWNLOAD_DIR, filename=filename)
                post_media = link_post_media_asset(db=db, post=post, media_asset=media_asset, position=i)
                post_medias.append(post_media)

        return post_medias
