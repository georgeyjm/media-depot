from typing import Dict, Any, Callable, TypeVar, Protocol
from importlib import import_module
import os
from pathlib import Path

# Define handler function signatures
class HandlerModule(Protocol):
    @staticmethod
    def is_supported(url: str) -> bool: ...
    
    @staticmethod
    def extract_info(url: str) -> Dict[str, Any]: ...
    
    @staticmethod
    def download(url: str, output_path: str) -> str: ...

# Type variable for handler modules
T = TypeVar('T', bound=HandlerModule)

# Dictionary to store handler modules
HANDLERS: Dict[str, HandlerModule] = {}

def _discover_handlers() -> None:
    """Discover and import all handler modules in the handlers directory."""
    handlers_dir = Path(__file__).parent
    
    for file in handlers_dir.glob('*_handler.py'):
        module_name = file.stem
        if module_name == 'handler_factory':
            continue
            
        try:
            module = import_module(f'.{module_name}', 'handlers')
            if hasattr(module, 'is_supported') and hasattr(module, 'extract_info') and hasattr(module, 'download'):
                # Use the module name without '_handler' as the key
                handler_name = module_name.replace('_handler', '')
                HANDLERS[handler_name] = module
        except ImportError as e:
            print(f"Error importing handler {module_name}: {e}")

def get_handler_for_url(url: str) -> HandlerModule:
    """
    Get the appropriate handler module for the given URL.
    
    Args:
        url: The video URL to find a handler for
        
    Returns:
        The handler module that supports the URL
        
    Raises:
        ValueError: If no handler is found for the URL
    """
    for handler in HANDLERS.values():
        if handler.is_supported(url):
            return handler
    raise ValueError(f"No handler found for URL: {url}")

def get_handler(name: str) -> HandlerModule:
    """
    Get a handler by name.
    
    Args:
        name: The name of the handler (e.g., 'youtube', 'tiktok')
        
    Returns:
        The handler module
        
    Raises:
        ValueError: If no handler is found with the given name
    """
    if name not in HANDLERS:
        raise ValueError(f"No handler found with name: {name}")
    return HANDLERS[name]

def register_handler(name: str, handler_module: HandlerModule) -> None:
    """
    Register a new handler module.
    
    Args:
        name: The name to register the handler under
        handler_module: The handler module to register
    """
    HANDLERS[name] = handler_module

# Initialize handlers on import
_discover_handlers()



'''
from typing import Dict, Type
from .base_handler import BaseVideoHandler
from .youtube_handler import YouTubeHandler
from .tiktok_handler import TikTokHandler

# Initialize handlers
HANDLERS: Dict[str, Type[BaseVideoHandler]] = {
    'youtube': YouTubeHandler,
    'tiktok': TikTokHandler
}

def get_video_handler(url: str) -> BaseVideoHandler:
    """Get the appropriate handler for the given URL"""
    for handler_class in HANDLERS.values():
        handler = handler_class()
        if handler.is_supported(url):
            return handler
    raise ValueError(f"No handler found for URL: {url}")

def register_video_handler(name: str, handler_class: Type[BaseVideoHandler]):
    """Register a new video handler"""
    HANDLERS[name] = handler_class
'''