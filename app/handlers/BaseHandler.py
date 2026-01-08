import re
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Any, Optional, ClassVar

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Platform, MediaAsset
from app.models.enums import PostType


class BaseHandler(ABC):
    '''Base class for all platform handlers.'''

    PLATFORM_NAME: ClassVar[str] = ''
    PLATFORM_DISPLAY_NAME: ClassVar[str] = ''
    FULL_URL_PATTERNS: ClassVar[tuple[str, ...]] = ()
    SHORT_URL_PATTERNS: ClassVar[tuple[str, ...]] = ()
    CREATOR_URL_PATTERN: ClassVar[str] = ''
    # Set during initialization
    PLATFORM: ClassVar[Optional[Platform]] = None
    DOWNLOAD_DIR: ClassVar[Optional[Path]] = None

    def __init__(self):
        self.client = httpx.Client(
            headers={
                # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1 Edg/143.0.0.0'
            },
            follow_redirects=True,
            timeout=15.0,
        )
        # Instance state for cached page content
        self._current_url: Optional[str] = None
        self._resolved_url: Optional[str] = None
        self._response: Optional[httpx.Response] = None
        self._html: Optional[str] = None
        self._soup: Optional[BeautifulSoup] = None
    
    def __del__(self):
        '''Close the httpx client when handler is destroyed.'''
        self.client.close()
    
    def clear_cache(self) -> None:
        '''Clear the cached page content.'''
        self._current_url = None
        self._resolved_url = None
        self._response = None
        self._html = None
    
    @classmethod
    def supports_share(cls, share_text: str) -> bool:
        '''Check if the share text contains a supported URL.'''
        return any(re.search(pattern, share_text) for pattern in cls.FULL_URL_PATTERNS + cls.SHORT_URL_PATTERNS)
    
    @classmethod
    def extract_url_from_share(cls, share_text: str) -> str | None:
        '''Extract the URL from the share text.'''
        for pattern in cls.FULL_URL_PATTERNS + cls.SHORT_URL_PATTERNS:
            if match := re.search(pattern, share_text):
                return match.group(0)
        return None

    @classmethod
    def ensure_platform_exists(cls, db: Session) -> Platform:
        '''
        Ensure the Platform record exists in the database for this handler.
        Creates it if it doesn't exist.
        Also stores the Platform object as a class variable for easy access.
        
        Args:
            db: Database session
            
        Returns:
            Platform instance (existing or newly created)
            
        Raises:
            ValueError: If PLATFORM_NAME is not set
        '''
        if not cls.PLATFORM_NAME:
            raise ValueError(f'Handler {cls.__name__} does not have PLATFORM_NAME set')
        
        # Try to get existing platform
        platform = db.query(Platform).filter_by(name=cls.PLATFORM_NAME).first()
        
        if not platform:
            # Create new platform
            platform = Platform(
                name=cls.PLATFORM_NAME,
                display_name=cls.PLATFORM_DISPLAY_NAME or ''  # cls.PLATFORM_NAME.title()
            )
            db.add(platform)
            db.flush()  # Get platform.id
        
        # Initialize class variables
        cls.PLATFORM = platform
        cls.DOWNLOAD_DIR = settings.MEDIA_ROOT_DIR / platform.name
        cls.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        return platform


    def load(self, url: str) -> str:
        '''
        Load and cache the page content for a URL.
        This should be called once before using other methods.
        
        Args:
            url: The URL to load (can be share URL or actual URL)
        
        Returns:
            str: The resolved actual post URL
        
        Raises:
            httpx.RequestError: If the URL cannot be loaded
        '''
        # If already loaded, return cached resolved URL
        if self._current_url == url and self._resolved_url:
            return self._resolved_url
        
        response = self.client.get(url)
        response.raise_for_status()
        
        # Cache everything
        self._current_url = url
        self._resolved_url = str(response.url)
        self._response = response
        self._html = response.text
        
        return self._resolved_url
    
    # def _ensure_loaded(self, url: str) -> None:
    #     '''
    #     Ensure page content is loaded. If not, load it automatically.
        
    #     Args:
    #         url: The URL that should be loaded
    #     '''
    #     if self._current_url != url or not self._html:
    #         self.load(url)
    
    # def resolve_url(self, url: str) -> str:
    #     '''Resolve a share URL to the actual post URL.'''
    #     # If already loaded, return cached resolved URL
    #     if self._current_url == url and self._resolved_url:
    #         return self._resolved_url
        
    #     # Otherwise, load it
    #     return self.load(url)
    

    @abstractmethod
    def get_post_type(self, url: str) -> PostType:
        '''Determine the type of post (video, carousel, etc.).
        
        Args:
            url: The actual post URL (should be resolved first via load() or resolve_url())
            
        Returns:
            PostType: The type of post (video, carousel, or unknown)
        '''
        pass

    @abstractmethod
    def extract_info(self, url: str, html: str, share_url: Optional[str]) -> dict[str, Any]:
        '''Platform-specific implementation of extract_info.'''
        pass

    @abstractmethod
    def extract_media_urls(self, url: str) -> list[dict[str, Any]]:
        '''Extract all media URLs from the post.
        
        Args:
            url: The actual post URL (should be resolved first via load() or resolve_url())
            
        Returns:
            List of dicts with media information
        '''
        pass

    @abstractmethod
    def download(self) -> list[MediaAsset]:
        '''Download all media from the post.'''
        pass
    
    # def process(self, url: str) -> dict[str, Any]:
    #     '''
    #     Process a URL completely in one go: load once, then extract everything.
        
    #     Args:
    #         url: The URL to process (can be share URL or actual URL)
        
    #     Returns:
    #         Dict containing:
    #         - info: Post metadata
    #         - media_urls: List of media URLs
    #     '''
    #     # Load once
    #     resolved_url = self.load(url)
    #     share_url = url if url != resolved_url else None
        
    #     # Extract everything using cached HTML
    #     info = self._extract_info_impl(resolved_url, self._html, share_url)
    #     info['post_type'] = self.get_post_type(resolved_url)
    #     media_urls = self.extract_media_urls(resolved_url)
        
    #     return {
    #         'info': info,
    #         'media_urls': media_urls
    #     }
