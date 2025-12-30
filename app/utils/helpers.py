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

