import logging
import sys
from app.core.config import settings

def setup_logging():
    """
    Configure the root logger based on settings.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if settings.LOG_TO_FILE:
        handlers.append(logging.FileHandler(settings.LOG_FILE_PATH))
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )
    
    # Set level for specific noisy libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
