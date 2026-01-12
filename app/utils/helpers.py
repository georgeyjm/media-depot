import re
from urllib.parse import urlsplit, urlunsplit


def remove_query_params(url: str) -> str:
    '''
    Remove all query parameters from a URL.
    
    Args:
        url: The URL string to clean
        
    Returns:
        The URL without query parameters
    '''
    parsed = urlsplit(url)
    cleaned = urlunsplit(parsed._replace(query='', fragment=''))
    return cleaned


def unescape_unicode(text: str) -> str:
    '''
    Unescape Unicode characters in a string.
    
    Args:
        text: The string to unescape
        
    Returns:
        The unescaped string
    '''
    return text.encode('utf-8').decode('unicode-escape')


def sanitize_filename(filename: str) -> str:
    '''
    Sanitize a filename to make it safe for filesystem operations and URLs.

    Removes characters that are:
    - Unsafe for filesystems: < > : " / \\ | ? *
    - Unsafe for URLs: # % & + = ; @ ! $ ' ( ) ,

    Args:
        filename: The filename to sanitize

    Returns:
        The sanitized filename
    '''
    return re.sub(r'[<>:"/\\|?*#%&+=;@!$\'(),]', '_', filename)
