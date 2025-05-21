"""
Video handler modules for different platforms.

This package contains modules that handle video downloading from different platforms.
Each module should implement the following functions:

- is_supported(url: str) -> bool
- extract_info(url: str) -> Dict[str, Any]
- download(url: str, output_path: str) -> str
"""

# Import the handler factory functions to make them easily accessible
from .handler_factory import get_handler_for_url, get_handler, register_handler

__all__ = ['get_handler_for_url', 'get_handler', 'register_handler']
