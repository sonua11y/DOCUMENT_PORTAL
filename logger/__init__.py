"""
Logger package initialization.
Provides a global logger instance for the application.
"""

from .custom_logger import CustomLogger

# Create a global logger instance
_custom_logger = CustomLogger()
GLOBAL_LOGGER = _custom_logger.get_logger("document_portal")

# Make it available at package level
__all__ = ["GLOBAL_LOGGER", "CustomLogger"]
