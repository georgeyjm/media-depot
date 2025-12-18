"""
Handler modules for different content platforms.

This package contains modules that handle content downloading from different platforms.
Each handler should inherit from BaseHandler and implement the required methods.
"""

from typing import Dict, Any, Type, List
from .BaseHandler import BaseHandler

# Import all handler modules
import importlib
import pkgutil
import inspect
import os

# Dictionary to store handler classes
HANDLERS: Dict[str, Type[BaseHandler]] = {}

# List of built-in handlers to import
BUILTIN_HANDLERS = [
    'BilibiliHandler',
    'DouyinHandler',
    'XhsHandler',
    'YoutubeHandler'
]

def get_handler_for_url(url: str) -> BaseHandler:
    """
    Get an instance of the appropriate handler for the given URL.
    
    Args:
        url: The content URL to find a handler for
        
    Returns:
        An instance of the handler class that supports the URL
        
    Raises:
        ValueError: If no handler is found for the URL
    """
    for handler_class in HANDLERS.values():
        if handler_class.is_supported(url):
            return handler_class()
    raise ValueError(f"No handler found for URL: {url}")

def get_handler(name: str) -> Type[BaseHandler]:
    """
    Get a handler class by name.
    
    Args:
        name: The name of the handler (e.g., 'youtube', 'tiktok')
        
    Returns:
        The handler class
        
    Raises:
        ValueError: If no handler is found with the given name
    """
    name = name.lower()
    if name not in HANDLERS:
        raise ValueError(f"No handler found with name: {name}")
    return HANDLERS[name]

def register_handler(name: str, handler_class: Type[BaseHandler]) -> None:
    """
    Register a new handler class.
    
    Args:
        name: The name to register the handler under (lowercase)
        handler_class: The handler class to register (must be a subclass of BaseHandler)
        
    Raises:
        TypeError: If handler_class is not a subclass of BaseHandler
    """
    if not (inspect.isclass(handler_class) and issubclass(handler_class, BaseHandler)):
        raise TypeError(f"Handler must be a subclass of BaseHandler, got {type(handler_class)}")
    
    name = name.lower()
    HANDLERS[name] = handler_class

def load_handlers() -> None:
    """
    Load all built-in handlers and any additional handlers from the handlers directory.
    This function is called automatically when the package is imported.
    """
    # Import built-in handlers
    for module_name in BUILTIN_HANDLERS:
        try:
            module = importlib.import_module(f'.{module_name}', __name__)
            # Find all handler classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseHandler) and 
                    obj is not BaseHandler and 
                    not inspect.isabstract(obj)):
                    # Register the handler using its class name (without 'Handler' suffix)
                    handler_name = module_name.replace('Handler', '').lower()
                    register_handler(handler_name, obj)
        except ImportError as e:
            print(f"Warning: Could not load handler {module_name}: {e}")

# Load all handlers when the package is imported
load_handlers()

__all__ = [
    'BaseHandler',
    'get_handler_for_url', 
    'get_handler', 
    'register_handler',
    'load_handlers'
]
