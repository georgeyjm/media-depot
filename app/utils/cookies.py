'''
Cookie management.

Kept separate from download.py so that host-side tooling (scripts/refresh_cookies.py)
can refresh cookies without importing the download stack, which needs libmagic.
'''

import time
from pathlib import Path
from typing import Any, Optional
from http.cookiejar import MozillaCookieJar

import httpx
from yt_dlp import YoutubeDL

from app.config import settings


# Module-level cache for cookie file path and last extraction time
_cookie_cache_info: dict[str, Any] = {
    'cookie_file': None,
    'last_extracted': None,
}

# Warnings we only want to print once per process
_emitted_cookie_warnings: set[str] = set()


def _warn_cookies_once(key: str, message: str) -> None:
    '''Print a cookie-related warning at most once per process, deduped by key.'''
    if key not in _emitted_cookie_warnings:
        _emitted_cookie_warnings.add(key)
        print(f'[cookies] {message}')


def refresh_cookies_from_browser(browser: Optional[str] = None, cookie_file: Optional[Path] = None) -> bool:
    '''
    Extract cookies from a local browser using yt-dlp and save them to a file.

    This only works where the browser's cookie store is readable - i.e. on the
    host machine, not inside a container, where the decryption key lives in the
    OS keychain. Containers should read a file refreshed on the host instead.

    Args:
        browser: Browser to extract from. Defaults to settings.COOKIES_FROM_BROWSER.
        cookie_file: Path where cookies should be saved. Defaults to settings.cookies_file.

    Returns:
        True if cookies were successfully extracted and saved, False otherwise.
    '''
    browser = browser or settings.COOKIES_FROM_BROWSER
    if not browser:
        return False
    return _extract_and_save_cookies(cookie_file or settings.cookies_file, browser)


def _extract_and_save_cookies(cookie_file: Path, browser: str) -> bool:
    '''
    Extract cookies from browser using yt-dlp and save them to a file.
    
    Args:
        cookie_file: Path where cookies should be saved.
        browser: Name of the browser to extract cookies from (e.g. 'edge', 'chrome').
        
    Returns:
        True if cookies were successfully extracted and saved, False otherwise.
    '''
    try:
        # Use yt-dlp with cookiesfrombrowser to extract cookies
        # We need to make a request to trigger cookie extraction
        extract_options = {
            'cookiesfrombrowser': (browser,),
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
                    ydl.cookiejar.save(str(cookie_file), ignore_discard=True, ignore_expires=True)
                else:
                    # If it's a different type, convert to MozillaCookieJar
                    mozilla_jar = MozillaCookieJar(str(cookie_file))
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

    When browser extraction is disabled (settings.COOKIES_FROM_BROWSER is None,
    which is what containers do) the cookie file is treated as read-only input
    that something outside this process keeps fresh.

    Returns:
        Path to the cookie file if available, None otherwise.
    '''
    cookie_file = settings.cookies_file
    current_time = time.time()

    file_exists = cookie_file.exists() and cookie_file.stat().st_size > 0
    file_age = current_time - cookie_file.stat().st_mtime if file_exists else None

    # Browser extraction disabled: use whatever file we were given, but say
    # something useful when it is missing or stale rather than failing silently.
    if not settings.COOKIES_FROM_BROWSER:
        if not file_exists:
            _warn_cookies_once(
                'missing',
                f'No cookie file at {cookie_file} and browser extraction is disabled. '
                f'Authenticated platforms will fail. Run scripts/refresh_cookies.py on the host.'
            )
            return None
        if file_age is not None and file_age > settings.COOKIES_REFRESH_INTERVAL:
            _warn_cookies_once(
                'stale',
                f'Cookie file {cookie_file} is {file_age / 3600:.1f}h old and cannot be '
                f'refreshed from here. Run scripts/refresh_cookies.py on the host if downloads fail.'
            )
        return cookie_file

    # Check if we need to refresh cookies
    needs_refresh = True
    if file_exists:
        if _cookie_cache_info['last_extracted'] is not None:
            # Check if cache is still valid
            time_since_extraction = current_time - _cookie_cache_info['last_extracted']
            if time_since_extraction < settings.COOKIES_REFRESH_INTERVAL:
                needs_refresh = False
        else:
            # Cookie file exists but we don't have timestamp info
            # Use file modification time as fallback
            if file_age is not None and file_age < settings.COOKIES_REFRESH_INTERVAL:
                needs_refresh = False
                _cookie_cache_info['last_extracted'] = cookie_file.stat().st_mtime

    if needs_refresh:
        # Extract cookies from browser and save to file
        if _extract_and_save_cookies(cookie_file, settings.COOKIES_FROM_BROWSER):
            _cookie_cache_info['last_extracted'] = current_time
            _cookie_cache_info['cookie_file'] = cookie_file
        else:
            # If extraction fails, check if old cookie file exists and is valid
            if file_exists:
                # Use old cookie file even though it's expired
                # This is better than falling back to browser extraction every time
                _warn_cookies_once(
                    'extract-failed-fallback',
                    f'Could not extract cookies from browser '
                    f'{settings.COOKIES_FROM_BROWSER!r}; using the existing {cookie_file}.'
                )
                return cookie_file
            # If no valid cookie file exists, return None to fall back to cookiesfrombrowser
            _warn_cookies_once(
                'extract-failed',
                f'Could not extract cookies from browser {settings.COOKIES_FROM_BROWSER!r} '
                f'and no cookie file exists at {cookie_file}.'
            )
            return None

    _cookie_cache_info['cookie_file'] = cookie_file
    # Verify cookie file exists and is not empty
    if cookie_file.exists() and cookie_file.stat().st_size > 0:
        return cookie_file
    return None


def get_all_cookies() -> httpx.Cookies | None:
    '''
    Get all cookies from the cookie file and return them in httpx.Cookies format.
    '''
    cookie_file = _get_cookie_file()
    if not (cookie_file and cookie_file.exists()):
        return None
    
    cookie_jar = MozillaCookieJar()
    cookie_jar.load(str(cookie_file), ignore_discard=True, ignore_expires=True)
    cookies = httpx.Cookies()
    for cookie in cookie_jar:
        cookies.set(cookie.name, cookie.value or '', domain=cookie.domain, path=cookie.path)
    return cookies
