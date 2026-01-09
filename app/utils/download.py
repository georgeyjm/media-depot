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
from app.utils.helpers import sanitize_filename


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


def _get_cookies(url: str) -> dict[str, str]:
    '''
    Get cookies for a given URL.
    
    Args:
        url: The URL to get cookies for.
    
    Returns:
        A dictionary of cookies.
    '''
    # Prepare cookies if needed
    cookie_file = _get_cookie_file()
    if cookie_file and cookie_file.exists():
        # Load cookies from file
        cookie_jar = MozillaCookieJar()
        cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
        
        # Filter cookies by domain to only include relevant cookies
        parsed_url = urlparse(url)
        request_domain = parsed_url.netloc.lower()
        # Remove port if present
        if ':' in request_domain:
            request_domain = request_domain.split(':')[0]
        
        # Filter cookies that match the request domain
        filtered_cookies = {}
        for cookie in cookie_jar:
            cookie_domain = cookie.domain.lower()
            
            # Check if cookie matches the request domain
            # Domain cookies (starting with '.') match the domain and all subdomains
            if cookie_domain.startswith('.'):
                # Remove leading dot for comparison
                base_domain = cookie_domain[1:]
                # Match exact domain or subdomains
                if request_domain == base_domain or request_domain.endswith('.' + base_domain):
                    filtered_cookies[cookie.name] = cookie.value
            else:
                # Non-domain cookies only match exact domain
                if request_domain == cookie_domain:
                    filtered_cookies[cookie.name] = cookie.value
        
        cookies = filtered_cookies if filtered_cookies else None
        return cookies


def download_yt_dlp(
    url: str,
    download_dir: Path=settings.MEDIA_ROOT_DIR,
    extra_options: dict[str, Any]={}
    ) -> Path:
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


def _determine_file_extension(response: httpx.Response, fallback: Optional[str] = None) -> str:
    '''
    Determine the file extension from the an HTTP response.
    
    Args:
        response: The HTTP response.
        fallback: The fallback extension to use if the extension cannot be determined otherwise.

    Returns:
        The file extension.
    '''
    # Try to infer from Content-Type header
    content_type = response.headers.get('Content-Type', '')
    extension = {
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/heic': '.heic',
        'image/heif': '.heif',
        'image/heic-sequence': '.heic',
        'image/heif-sequence': '.heif',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'video/mp4': '.mp4',
        'video/webm': '.webm',
        'video/hevc': '.hevc',
        'video/quicktime': '.mov',
        'video/x-msvideo': '.avi',
        'video/x-matroska': '.mkv',
        'video/x-m4v': '.m4v',
        'video/3gpp': '.3gp',
        'video/x-flv': '.flv',
        'video/x-ms-wmv': '.wmv',
    }.get(content_type, None)
    if extension:
        return extension
    
    # Try to extract from URL
    path_ext = Path(urlparse(str(response.url)).path).suffix
    if path_ext:
        extension = path_ext
    elif fallback:
        if fallback.startswith('.'):
            extension = fallback
        else:
            extension = '.' + fallback
    else:
        # This shouldn't happen
        extension = ''
    
    # Fix unwanted extensions
    extension = extension.replace('.jpeg', '.jpg')
    
    return extension


def _determine_filename(response: httpx.Response) -> str:
    '''
    Determine the filename from an HTTP response.
    
    Args:
        response: The HTTP response.
    '''
    # Try to extract filename from Content-Disposition header
    content_disposition = response.headers.get('Content-Disposition', '')
    filename = None
    if content_disposition:
        # Format: attachment; filename="file.jpg" or attachment; filename*=UTF-8''file.jpg
        filename_match = re.search(
            r'filename[*]?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?',
            content_disposition,
            re.IGNORECASE
        )
        if filename_match:
            filename = unquote(filename_match.group(1))
    
    # Extract filename from URL
    if not filename:
        parsed_url = urlparse(str(response.url))
        filename = Path(unquote(parsed_url.path)).name
    
    # If still no filename, generate one from hashing the URL
    if not filename or filename == '/':
        filename = hashlib.md5(str(response.url).encode()).hexdigest()[:8]
    
    return filename


def download_file(
    url: str,
    download_dir: Path = settings.MEDIA_ROOT_DIR,
    filename: Optional[str] = None,
    extension_fallback: Optional[str] = None,
    use_cookies: bool = False,
    chunk_size: int = 1024 * 1024,
    timeout: float = 60.0,
    headers: Optional[dict[str, str]] = None,
    overwrite: bool = False,
    retries: int = 8,
) -> Path:
    '''
    Download a file from an arbitrary URL with resume support.
    
    Args:
        url: The URL of the file to download.
        download_dir: The directory to download the file to. Defaults to MEDIA_ROOT_DIR.
        filename: Optional filename for the downloaded file (without extension). If not provided, will be
                  extracted from URL or Content-Disposition header.
        extension_fallback: Optional extension to use if the extension cannot be determined from the Content-Type header.
        use_cookies: Whether to use cookies from the cookie file. Defaults to False.
        chunk_size: Size of chunks to read in bytes. Defaults to 1MB.
        timeout: Request timeout in seconds. Defaults to 60.0. For large files, consider using a larger value (e.g., 600.0).
        headers: Optional custom headers to include in the request.
        overwrite: Whether to overwrite existing files. Defaults to False.
        retries: Number of retry attempts if resume is supported. Defaults to 8. If resume is not supported, only one attempt is made.
    
    Returns:
        Path: The path to the downloaded file.
    
    Raises:
        httpx.HTTPError: If the HTTP request fails.
        httpx.TimeoutException: If the request times out.
        ValueError: If filename cannot be determined.
    '''
    # Prepare request headers and cookies
    request_headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1 Edg/143.0.0.0',
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
        'Connection': 'keep-alive',
    }
    if headers:
        request_headers.update(headers)
    if use_cookies:
        cookies = _get_cookies(url)
    else:
        cookies = None
    
    # Default timeout is 60s, but for large files we should use at least 600s (10 minutes)
    httpx_timeout = httpx.Timeout(
        connect=10.0,
        read=timeout,
        write=15.0,
        pool=10.0,
    )
    # Set limits for download stability
    limits = httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5,
        keepalive_expiry=45.0,
    )
    
    extension = None
    file_path = None
    file_exists = False
    resume_supported = False
    expected_size = None
    
    with httpx.Client(cookies=cookies, timeout=httpx_timeout, limits=limits, follow_redirects=True) as client:
        try:
            # Make a HEAD request to check for resume support
            test_response = client.head(url, headers=request_headers, follow_redirects=True)
            test_response.raise_for_status()
            if test_response.headers.get('Accept-Ranges') == 'bytes':
                # Server supports Range requests
                resume_supported = True
                if not filename:
                    filename = _determine_filename(test_response)
                extension = _determine_file_extension(test_response, extension_fallback)
                expected_size = test_response.headers.get('Content-Length')  # TODO: Check this when download is finished
        except (httpx.HTTPStatusError, httpx.RequestError):
            # HEAD not supported or failed, we'll determine from GET response with Range header
            try:
                test_response = client.get(url, headers={'Range': 'bytes=0-0', **request_headers}, follow_redirects=True)
                if test_response.status_code == 206:  # Partial Content
                    resume_supported = True
                    if not filename and test_response.headers.get('Content-Disposition'):
                        filename = _determine_filename(test_response)
                    if test_response.headers.get('Content-Type'):
                        extension = _determine_file_extension(test_response, extension_fallback)
                    if content_range := test_response.headers.get('Content-Range'):
                        expected_size = int(content_range.split('/')[-1])
            except Exception:
                pass
        
        # Determine filename and extension by making a GET request
        if not filename or not extension or not expected_size:
            with client.stream('GET', url, headers=request_headers) as response:
                response.raise_for_status()
                if filename is None:
                    filename = _determine_filename(response)
                if extension is None:
                    extension = _determine_file_extension(response, extension_fallback)
                if expected_size is None:
                    expected_size = response.headers.get('Content-Length')
        
        # Determine final file name and path
        final_filename = sanitize_filename(filename + extension)
        if not final_filename:
            raise ValueError(f'Could not determine filename for URL: {url}')
        file_path = download_dir / final_filename
        file_exists = file_path.exists()
        
        # Handle existing files
        if file_exists:
            # Note this could be from a previous worker attempt to download the same file
            # Do we want to delete it?
            if overwrite:
                # Overwrite mode: delete existing file
                file_path.unlink()
                file_exists = False
            else:
                # Find a unique filename by appending a short UUID
                stem = file_path.stem
                suffix = file_path.suffix
                while file_path.exists():
                    unique_id = uuid.uuid4().hex[:8]
                    file_path = download_dir / f'{stem}_{unique_id}{suffix}'
                file_exists = False
        
        max_attempts = retries if resume_supported else 1
        
        last_exception = None
        for attempt in range(max_attempts):
            try:
                # Check if we should resume
                resume_from = 0
                if resume_supported and file_path.exists() and not overwrite:
                    file_size = file_path.stat().st_size
                    if file_size > 0:
                        resume_from = file_size
                        request_headers['Range'] = f'bytes={resume_from}-'
                
                with client.stream('GET', url, headers=request_headers) as response:
                    response.raise_for_status()
                    
                    file_mode = 'wb'  # Write mode
                    if resume_from > 0:
                        # Resuming from previous download
                        if response.status_code == 206:  # Partial Content
                            # Server supports range requests, resume successful
                            file_mode = 'ab'  # Append mode
                        elif response.status_code == 200:
                            # Server doesn't support range requests, restart download
                            file_mode = 'wb'  # Write mode
                            # Make a new request without the Range header
                            response.close()
                            request_headers.pop('Range', None)
                            with client.stream('GET', url, headers=request_headers) as response:
                                response.raise_for_status()
                                for chunk in response.iter_bytes(chunk_size=chunk_size):
                                    f.write(chunk)
                            return file_path
                        else:
                            response.raise_for_status()
                    
                    with file_path.open(file_mode) as f:
                        for chunk in response.iter_bytes(chunk_size=chunk_size):
                            f.write(chunk)
                    
                    return file_path
            
            except (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPStatusError) as e:
                last_exception = e
                # # If this is the last attempt, delete the file and re-raise
                # if attempt == max_attempts - 1:
                #     if file_path.exists() and not file_exists:
                #         try:
                #             file_path.unlink()
                #         except Exception:
                #             # Ignore errors during cleanup
                #             pass
                #     raise
                # # Otherwise, continue to next attempt (only if resume is supported)
                # if not resume_supported:
                #     # If resume is not supported, we only try once, so re-raise
                #     if file_path.exists() and not file_exists:
                #         try:
                #             file_path.unlink()
                #         except Exception:
                #             pass
                #     raise

                # Remove Range header for next attempt (will be re-added if file still exists)
                request_headers.pop('Range', None)
                time.sleep(2 * 2 ** attempt)
                continue
            except Exception as e:
                last_exception = e
                request_headers.pop('Range', None)
                time.sleep(2 * 2 ** attempt)
                continue
        
        # If we get here, all retries failed
        if file_path and file_path.exists() and not file_exists:
            try:
                file_path.unlink()
            except Exception:
                pass
        if last_exception:
            raise last_exception
        raise httpx.HTTPError(f'Failed to download {url} after {max_attempts} attempts')


def hash_file(
    file_path: Path,
    hash_type: Literal['sha256', 'md5', 'sha1'] = 'sha256',
    buffer_size: Optional[int] = None,
) -> str:
    '''
    Hash a file using specified hash algorithm.
    Note that when dealing with relatively small files, no buffers are needed.
    
    Args:
        file_path: The path to the file to hash.
        hash_type: The hash algorithm to use. Defaults to SHA-256.
        buffer_size: The buffer size to use for reading the file. If None, the file will be read in one go.
    
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
