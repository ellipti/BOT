import sys
from loguru import logger

# Global flag to track if logger is configured
_is_configured = False

def _configure_logger():
    """Configure logger with handlers if not already configured"""
    global _is_configured
    if _is_configured:
        return
    
    # Remove default handler
    logger.remove()
    
    # Add console handler with custom format
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file handler for all logs
    logger.add(
        "logs/trading_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # New file daily
        retention="30 days",  # Keep logs for 30 days
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )
    
    _is_configured = True

def setup_logger():
    """Legacy function: Configure and return logger instance"""
    _configure_logger()
    return logger

def get_logger(name: str = "main"):
    """Get a logger instance with the given name"""
    _configure_logger()
    return logger.bind(name=name)
