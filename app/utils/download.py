import time
import hashlib
from pathlib import Path
from typing import Any, Optional, Literal
from http.cookiejar import MozillaCookieJar

from yt_dlp import YoutubeDL

from app.config import settings


# Module-level cache for cookie file path and last extraction time
_cookie_cache_info: dict[str, Any] = {
    'cookie_file': None,
    'last_extracted': None,
}


def _extract_and_save_cookies(cookie_file: Path) -> bool:
    '''
    Extract cookies from browser using yt-dlp and save them to a file.
    
    Args:
        cookie_file: Path where cookies should be saved.
        
    Returns:
        True if cookies were successfully extracted and saved, False otherwise.
    '''
    try:
        # Use yt-dlp with cookiesfrombrowser to extract cookies
        # We need to make a request to trigger cookie extraction
        extract_options = {
            'cookiesfrombrowser': ('edge',),
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        
        # Make a request to bilibili.com to populate the cookie jar
        # This will trigger cookie extraction from the browser
        with YoutubeDL(extract_options) as ydl:
            # try:
            #     # Try to extract info from bilibili.com to populate cookies
            #     # We don't need a specific video, just need to trigger cookie extraction
            #     ydl.extract_info('https://www.bilibili.com/', download=False)
            # except Exception:
            #     # Even if extraction fails, cookies might still be populated
            #     # yt-dlp extracts cookies before making the request
            #     pass
            
            # Save cookies to file in Netscape format
            # yt-dlp uses http.cookiejar.MozillaCookieJar or similar
            if hasattr(ydl, 'cookiejar') and ydl.cookiejar:
                cookie_file.parent.mkdir(parents=True, exist_ok=True)
                # Save cookies in Netscape format
                if isinstance(ydl.cookiejar, MozillaCookieJar):
                    ydl.cookiejar.save(cookie_file, ignore_discard=True, ignore_expires=True)
                else:
                    # If it's a different type, convert to MozillaCookieJar
                    mozilla_jar = MozillaCookieJar(cookie_file)
                    for cookie in ydl.cookiejar:
                        mozilla_jar.set_cookie(cookie)
                    mozilla_jar.save(ignore_discard=True, ignore_expires=True)
                return True
    
    except Exception:
        # If extraction fails, return False
        return False
    
    return False


def _get_cookie_file() -> Optional[Path]:
    '''
    Get the path to the cached cookie file, extracting from browser if needed.
    
    Returns:
        Path to the cookie file if available, None otherwise.
    '''
    cookie_file = settings.CACHE_DIR / 'cookies.txt'
    current_time = time.time()
    
    # Check if we need to refresh cookies
    needs_refresh = True
    if cookie_file.exists():
        if _cookie_cache_info['last_extracted'] is not None:
            # Check if cache is still valid
            time_since_extraction = current_time - _cookie_cache_info['last_extracted']
            if time_since_extraction < settings.COOKIES_REFRESH_INTERVAL:
                needs_refresh = False
        else:
            # Cookie file exists but we don't have timestamp info
            # Use file modification time as fallback
            file_mtime = cookie_file.stat().st_mtime
            time_since_modification = current_time - file_mtime
            if time_since_modification < settings.COOKIES_REFRESH_INTERVAL:
                needs_refresh = False
                _cookie_cache_info['last_extracted'] = file_mtime
    
    if needs_refresh:
        # Extract cookies from browser and save to file
        if _extract_and_save_cookies(cookie_file):
            _cookie_cache_info['last_extracted'] = current_time
            _cookie_cache_info['cookie_file'] = cookie_file
        else:
            # If extraction fails, check if old cookie file exists and is valid
            if cookie_file.exists() and cookie_file.stat().st_size > 0:
                # Use old cookie file even though it's expired
                # This is better than falling back to browser extraction every time
                return cookie_file
            # If no valid cookie file exists, return None to fall back to cookiesfrombrowser
            return None
    
    _cookie_cache_info['cookie_file'] = cookie_file
    # Verify cookie file exists and is not empty
    if cookie_file.exists() and cookie_file.stat().st_size > 0:
        return cookie_file
    return None


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
    cookie_file = _get_cookie_file()
    ydl_options = {
        'paths': {'home': str(download_dir)},  # Note yt_dlp will create the download_dir directory if it doesn't exist
        'outtmpl': '[%(id)s] %(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
        'cookiefile': str(cookie_file),
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
