"""YouTube video handler module."""
from typing import Dict, Any
import re
import youtube_dl

def is_supported(url: str) -> bool:
    """Check if URL is a YouTube URL."""
    youtube_patterns = [
        r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+$',
        r'^https?://(?:www\.)?youtube\.com/shorts/[\w-]+$',
        r'^https?://(?:www\.)?youtu\.be/[\w-]+$'
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)

def extract_info(url: str) -> Dict[str, Any]:
    """Extract video information using youtube-dl."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True
    }
    
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', 'Untitled'),
            'description': info.get('description', ''),
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration', 0)
        }

def download(url: str, output_path: str) -> str:
    """Download YouTube video using youtube-dl."""
    ydl_opts = {
        'format': 'best',
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'quiet': True
    }
    
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        return output_path
