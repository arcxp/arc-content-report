"""
Utility functions for Arc XP Content Reports
"""
import functools
import logging
import time
import os
import psutil
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp


class PerformanceBenchmark:
    """Utility class for benchmarking code performance"""
    
    def __init__(self, name: str = "Benchmark"):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        duration = self.end_time - self.start_time
        memory_used = self.end_memory - self.start_memory
        
        logger = logging.getLogger(__name__)
        logger.info(f"{self.name}: Duration: {duration:.2f}s, Memory: {memory_used:.2f}MB")
        
        return False  # Don't suppress exceptions


def benchmark(func: Callable) -> Callable:
    """Decorator to benchmark function performance"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with PerformanceBenchmark(f"Function {func.__name__}"):
            return func(*args, **kwargs)
    return wrapper


def setup_logging(log_name: str, log_level: str = "INFO") -> logging.Logger:
    """Setup logging configuration with file and console handlers"""
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(log_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_handler = logging.FileHandler(f"logs/{log_name}.log")
    # file_handler = logging.FileHandler(f"logs/{log_name}_{timestamp}.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def ensure_spreadsheets_dir():
    """Ensure the spreadsheets directory exists"""
    os.makedirs("spreadsheets", exist_ok=True)


def get_csv_path(filename: str) -> str:
    """Get the full path for a CSV file in the spreadsheets directory"""
    ensure_spreadsheets_dir()
    return os.path.join("spreadsheets", filename)


def ensure_databases_dir():
    """Ensure the databases directory exists"""
    os.makedirs("databases", exist_ok=True)


def get_db_path(db_name: str) -> str:
    """Get the full path for a database file in the databases directory"""
    ensure_databases_dir()
    return os.path.join("databases", db_name)


class RateLimiter:
    """Simple rate limiter to avoid overwhelming APIs"""
    
    def __init__(self, max_requests_per_second: int = 10):
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()


def format_timestamp(timestamp_ms: int) -> str:
    """Convert millisecond timestamp to readable format"""
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


# Original functions for backward compatibility
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