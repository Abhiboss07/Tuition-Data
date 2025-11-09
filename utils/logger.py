import logging
import sys
from rich.logging import RichHandler
from rich.console import Console

# Use console with UTF-8 encoding for Windows
console = Console(force_terminal=True, force_interactive=False)

def setup_logger(name: str = "TuitionDataCollector", level: int = logging.INFO):
    """
    Setup a rich logger with colored output
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Rich handler for console output
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True
    )
    rich_handler.setLevel(level)
    
    # Formatter
    formatter = logging.Formatter(
        "%(message)s",
        datefmt="[%X]"
    )
    rich_handler.setFormatter(formatter)
    
    # Add handler
    logger.addHandler(rich_handler)
    
    # Also log to file (with UTF-8 encoding)
    file_handler = logging.FileHandler('scraper.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)
    
    return logger

# Global logger instance
logger = setup_logger()
