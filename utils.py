"""
Utility functions for Arc XP Org Redirects Reports
"""
import functools
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
import os

# Configure logging
def setup_logging(log_level: str = "INFO", log_file: str = "logs/redirects.log") -> logging.Logger:
    """Setup logging configuration for the redirects report scripts."""
    os.makedirs("logs", exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def timing_decorator(func: Callable) -> Callable:
    """Decorator to measure execution time of functions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger = logging.getLogger(func.__module__)
        logger.info(f"Starting {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"Completed {func.__name__} in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.error(f"Error in {func.__name__} after {execution_time:.2f} seconds: {str(e)}")
            raise
    
    return wrapper

def log_api_call(func: Callable) -> Callable:
    """Decorator to log API call details and performance."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            response_time = end_time - start_time
            
            # Extract relevant info for logging
            if hasattr(result, 'status_code'):
                status_code = result.status_code
                logger.info(f"API call {func.__name__} completed with status {status_code} in {response_time:.2f}s")
            else:
                logger.info(f"API call {func.__name__} completed in {response_time:.2f}s")
            
            return result
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            logger.error(f"API call {func.__name__} failed after {response_time:.2f}s: {str(e)}")
            raise
    
    return wrapper

def format_date_range(start_date: str, end_date: str) -> str:
    """Format date range for logging and file naming."""
    return f"{start_date}_to_{end_date}"

def create_output_filename(prefix: str, start_date: str, end_date: str, website: str, suffix: str = "csv") -> str:
    """Create standardized output filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_range = format_date_range(start_date, end_date)
    filename=f"{date_range}_{website}.{suffix}"
    # filename=f"{date_range}_{website}_{timestamp}.{suffix}"
    if prefix:
        return f"{prefix}_{filename}"
    return f"{filename}"

def validate_date_format(date_str: str) -> bool:
    """Validate date string format."""
    try:
        datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False

def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split a list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)] 