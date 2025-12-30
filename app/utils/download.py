import hashlib
from typing import Any, Optional, Literal
from pathlib import Path

from yt_dlp import YoutubeDL

from app.config import settings


def download_yt_dlp(url: str, download_dir: Path=settings.MEDIA_ROOT_DIR, extra_options: dict[str, Any]={}) -> Path:
    '''
    Download a video using yt-dlp.

    Args:
        url: The URL of the video to download.
        download_dir: The directory to download the video to.
        extra_options: Extra options to pass to yt-dlp.
    
    Returns:
        Path: The path to the downloaded video.
    '''
    # Note yt_dlp will create the download_dir directory if it doesn't exist
    ydl_options = {
        'paths': {'home': str(download_dir)},
        'outtmpl': '[%(id)s] %(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
    }
    ydl_options.update(extra_options)
    with YoutubeDL(ydl_options) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
    return Path(file_path)


def hash_file(file_path: Path, buffer_size: Optional[int]=None, hash_type: Literal['sha256', 'md5', 'sha1']='sha256') -> str:
    '''
    Hash a file using specified hash algorithm.
    Note that when dealing with relatively small files, no buffers are needed.
    
    Args:
        file_path: The path to the file to hash.
        buffer_size: The buffer size to use for reading the file. If None, the file will be read in one go.
        hash_type: The hash algorithm to use. Defaults to SHA-256.
    
    Returns:
        str: The SHA-256 hash of the file.
    '''
    with file_path.open('rb', buffering=0) as f:
        if buffer_size is None:
            hash_value = hashlib.file_digest(f, hash_type).hexdigest()
        else:
            hash_func = getattr(hashlib, hash_type)
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                hash_func.update(data)
            hash_value = hash_func.hexdigest()
    return hash_value
