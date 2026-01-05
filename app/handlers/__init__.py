from typing import Type

from sqlalchemy.orm import Session

from app.handlers.BaseHandler import BaseHandler
from app.handlers.BilibiliHandler import BilibiliHandler
from app.handlers.DouyinHandler import DouyinHandler
# from app.handlers.XhsHandler import XhsHandler
# from app.handlers.YoutubeHandler import YoutubeHandler


# List of all available handler classes
HANDLERS: list[Type[BaseHandler]] = [
    BilibiliHandler,
    DouyinHandler,
    # XhsHandler,
    # YoutubeHandler,
]


def get_handler_from_share(share_text: str) -> BaseHandler | None:
    '''
    Get an instance of the appropriate handler for the given share text.
    
    Args:
        share_text: Any share text containing a post URL
        
    Returns:
        The handler instance
    '''
    for handler_class in HANDLERS:
        if handler_class.supports_share(share_text):
            return handler_class()
    return None


def extract_url_from_share(share_text: str) -> str | None:
    '''
    Extract the URL from the share text.
    
    Args:
        share_text: Any share text containing a post URL
        
    Returns:
        The extracted URL
    '''
    for handler_class in HANDLERS:
        if url := handler_class.extract_url_from_share(share_text):
            return url
    return None


def initialize_platforms(db: Session) -> None:
    '''
    Ensure all platforms from registered handlers exist in the database.
    This should be called once during application startup.
    Also stores the Platform object as a class variable on each handler class.
    
    Args:
        db: Database session
    '''
    for handler_class in HANDLERS:
        assert issubclass(handler_class, BaseHandler)
        assert handler_class.PLATFORM_NAME
        handler_class.ensure_platform_exists(db)
    db.commit()


__all__ = [
    'BaseHandler',
    'BilibiliHandler',
    'DouyinHandler',
    'HANDLERS',
    'get_handler_from_share',
    'extract_url_from_share',
    'initialize_platforms',
]
