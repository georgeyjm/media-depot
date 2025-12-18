from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os

class BaseHandler(ABC):
    """Base class for all platform handlers."""
    
    @classmethod
    @abstractmethod
    def is_supported(cls, url: str) -> bool:
        """Check if this handler can process the given URL.
        
        Args:
            url: The URL to check
            
        Returns:
            bool: True if this handler can process the URL, False otherwise
        """
        pass
    
    @abstractmethod
    def extract_info(self, url: str) -> Dict[str, Any]:
        """Extract information from the given URL.
        
        Args:
            url: The URL to extract information from
            
        Returns:
            Dict containing post information with the following keys:
            - platform_id: Unique ID of the post on the platform
            - platform: Platform name (e.g., 'youtube', 'tiktok')
            - post_type: One of Post.TYPE_* constants
            - title: Post title
            - description: Post description (optional)
            - creator_id: Platform-specific creator ID
            - creator_username: Creator's username
            - creator_avatar: URL to creator's avatar (optional)
            - thumbnail_url: URL to post thumbnail (optional)
            - media_url: Direct URL to media file (if applicable)
            - duration: Duration in seconds (for video/audio, optional)
            - width: Media width in pixels (for images/videos, optional)
            - height: Media height in pixels (for images/videos, optional)
            - created_at: When the post was created (datetime, optional)
        """
        pass
    
    def should_download_media(self) -> bool:
        """
        Determine if the media should be downloaded.
        
        Override this in subclasses if the platform supports downloading media.
        
        Returns:
            bool: True if the media should be downloaded, False otherwise
        """
        return False
    
    def download(self, url: str, output_path: str) -> Optional[str]:
        """
        Download the media to the specified path.
        
        Args:
            url: The URL of the post
            output_path: Directory where the media should be saved
            
        Returns:
            str: Path to the downloaded file, or None if download is not supported
            
        Raises:
            NotImplementedError: If the platform doesn't support downloading
        """
        raise NotImplementedError("This platform does not support downloading media")
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize a filename to be filesystem-safe.
        
        Args:
            filename: The original filename
            
        Returns:
            str: Sanitized filename
        """
        # Replace any character that's not alphanumeric, space, dot, or dash with underscore
        return "".join(c if c.isalnum() or c in ' ._-' else '_' for c in filename)
    
    @staticmethod
    def get_extension_from_url(url: str) -> str:
        """
        Extract file extension from URL.
        
        Args:
            url: The URL to extract extension from
            
        Returns:
            str: File extension (without dot), or 'bin' if cannot determine
        """
        # Remove query parameters and fragments
        clean_url = url.split('?')[0].split('#')[0]
        
        # Get the last part after the last dot
        if '.' in clean_url:
            ext = clean_url.rsplit('.', 1)[1].lower()
            # Remove any path components that might be in the extension
            ext = ext.split('/')[0]
            if ext and len(ext) <= 10:  # Reasonable max length for file extensions
                return ext
        return 'bin'  # Default extension if none found
