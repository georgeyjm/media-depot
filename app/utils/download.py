import time
import hashlib
import re
import uuid
from pathlib import Path
from typing import Any, Optional, Literal
from http.cookiejar import MozillaCookieJar
from urllib.parse import urlparse, unquote

import httpx
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


def download_file(
    url: str,
    download_dir: Path = settings.MEDIA_ROOT_DIR,
    filename: Optional[str] = None,
    use_cookies: bool = False,
    timeout: float = 30.0,
    headers: Optional[dict[str, str]] = None,
) -> Path:
    '''
    Download a file from a URL to a local directory.
    
    Args:
        url: The URL of the file to download.
        download_dir: The directory to download the file to. Defaults to MEDIA_ROOT_DIR.
        filename: Optional filename for the downloaded file. If not provided, will be
                  extracted from URL or Content-Disposition header.
        use_cookies: Whether to use cookies from the cookie file. Defaults to False.
        timeout: Request timeout in seconds. Defaults to 30.0.
        headers: Optional custom headers to include in the request.
    
    Returns:
        Path: The path to the downloaded file.
    
    Raises:
        httpx.HTTPError: If the HTTP request fails.
        httpx.TimeoutException: If the request times out.
        ValueError: If filename cannot be determined.
    '''
    # Ensure download directory exists
    download_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare request headers
    request_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    if headers:
        request_headers.update(headers)
    
    # Prepare cookies if needed
    cookies = None
    if use_cookies:
        cookie_file = _get_cookie_file()
        if cookie_file and cookie_file.exists():
            # Load cookies from file
            cookie_jar = MozillaCookieJar()
            cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
            cookies = dict(cookie_jar)
    
    with httpx.Client(cookies=cookies, timeout=timeout, follow_redirects=True) as client:
        with client.stream('GET', url, headers=request_headers) as response:
            response.raise_for_status()

            # Determine file extension
            content_type = response.headers.get('Content-Type', '')
            if 'image/jpeg' in content_type or 'image/jpg' in content_type:
                extension = '.jpg'
            elif 'image/png' in content_type:
                extension = '.png'
            elif 'image/gif' in content_type:
                extension = '.gif'
            elif 'image/webp' in content_type:
                extension = '.webp'
            else:
                # Try to extract from URL
                parsed_url = urlparse(url)
                path_ext = Path(parsed_url.path).suffix
                extension = path_ext if path_ext else ''

            # Determine filename
            if filename:
                final_filename = filename + extension
            else:
                # Try to get filename from Content-Disposition header
                content_disposition = response.headers.get('Content-Disposition', '')
                if content_disposition:
                    # Extract filename from Content-Disposition header
                    # Format: attachment; filename="file.jpg" or attachment; filename*=UTF-8''file.jpg
                    filename_match = re.search(
                        r'filename[*]?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?',
                        content_disposition,
                        re.IGNORECASE
                    )
                    if filename_match:
                        final_filename = unquote(filename_match.group(1))
                    else:
                        # Fallback: extract from URL
                        parsed_url = urlparse(url)
                        final_filename = Path(unquote(parsed_url.path)).name
                else:
                    # Extract filename from URL
                    parsed_url = urlparse(url)
                    final_filename = Path(unquote(parsed_url.path)).name
                
                # If still no filename, generate one from URL
                if not final_filename or final_filename == '/':
                    # Generate filename from URL hash or use a default
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                    final_filename = url_hash + extension
            
            # Ensure filename is safe
            final_filename = re.sub(r'[<>:"/\\|?*]', '_', final_filename)
            if not final_filename:
                raise ValueError(f'Could not determine filename for URL: {url}')
            
            # Ensure we don't overwrite existing files
            file_path = download_dir / final_filename
            if file_path.exists():
                # Find a unique filename by appending a short UUID
                stem = file_path.stem
                suffix = file_path.suffix
                while file_path.exists():
                    unique_id = uuid.uuid4().hex[:8]
                    file_path = download_dir / f'{stem}_{unique_id}{suffix}'
            
            # Stream the file content to disk
            with file_path.open('wb') as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
            
            return file_path


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
