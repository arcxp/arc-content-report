"""
Date Range Builder for Arc XP Org Redirects Report
Automatically splits large date ranges to satisfy API limits
"""
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import requests
from ratelimit import limits, sleep_and_retry
from utils import log_api_call, setup_logging

logger = logging.getLogger(__name__)

class DateRangeBuilder:
    """Handles automatic date range splitting for API calls."""
    
    def __init__(self, bearer_token: str, org: str, website: str, environment: str = "production"):
        self.bearer_token = bearer_token
        self.org = org if environment == "production" else f"sandbox.{org}"
        self.website = website
        self.env = environment
        self.arc_auth_header = {
            "Authorization": f"Bearer {self.bearer_token}", 
            "User-Agent": f"python-requests-{self.org}-script-arcxp"
        }
        self.max_records = 10000  # API limit
        self.max_recursion_depth = 10  # Prevent infinite recursion
        
    @property
    def search_url(self) -> str:
        return f"https://api.{self.org}.arcpublishing.com/content/v4/search"
    
    @log_api_call
    @sleep_and_retry
    @limits(calls=20, period=60)
    def get_total_hits(self, start_date: str, end_date: str) -> int:
        """Get total number of hits for a date range."""
        search_q = f"type:redirect AND created_date:[{start_date} TO {end_date}]"
        
        params = {
            "website": self.website,
            "track_total_hits": "true",
            "q": search_q,
            "size": "1",  # We only need the count
            "from": "0"
        }
        
        try:
            response = requests.get(self.search_url, headers=self.arc_auth_header, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("count", 0)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get total hits for {start_date} to {end_date}: {e}")
            return 0
    
    def split_range(self, start_date: str, end_date: str, depth: int = 0) -> List[Tuple[str, str]]:
        """
        Recursively split date range if it exceeds API limits.
        
        Args:
            start_date: Start date in ISO format
            end_date: End date in ISO format
            depth: Current recursion depth
            
        Returns:
            List of (start_date, end_date) tuples
        """
        if depth >= self.max_recursion_depth:
            logger.warning(f"Max recursion depth reached for {start_date} to {end_date}")
            return [(start_date, end_date)]
        
        logger.info(f"Checking date range {start_date} to {end_date} (depth: {depth})")
        
        # Get total hits for this range
        total_hits = self.get_total_hits(start_date, end_date)
        logger.info(f"Total hits for {start_date} to {end_date}: {total_hits}")
        
        # If within limits, return as single range
        if total_hits <= self.max_records:
            logger.info(f"Range {start_date} to {end_date} is within limits ({total_hits} hits)")
            return [(start_date, end_date)]
        
        # If exceeds limits, split at midpoint
        logger.info(f"Range {start_date} to {end_date} exceeds limits ({total_hits} hits), splitting...")
        
        # Parse dates
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Calculate midpoint
        midpoint = start_dt + (end_dt - start_dt) / 2
        
        # Format midpoint for API
        midpoint_str = midpoint.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Recursively split both halves
        first_half = self.split_range(start_date, midpoint_str, depth + 1)
        second_half = self.split_range(midpoint_str, end_date, depth + 1)
        
        return first_half + second_half
    
    def build_optimal_ranges(self, start_date: str, end_date: str) -> List[Tuple[str, str]]:
        """
        Build optimal date ranges for API calls.
        
        Args:
            start_date: Start date in ISO format
            end_date: End date in ISO format
            
        Returns:
            List of (start_date, end_date) tuples optimized for API limits
        """
        logger.info(f"Building optimal date ranges from {start_date} to {end_date}")
        
        ranges = self.split_range(start_date, end_date)
        
        logger.info(f"Generated {len(ranges)} optimal date ranges:")
        for i, (start, end) in enumerate(ranges, 1):
            logger.info(f"  Range {i}: {start} to {end}")
        
        return ranges
    
    def validate_date_range(self, start_date: str, end_date: str) -> bool:
        """Validate that start_date is before end_date."""
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            return start_dt < end_dt
        except ValueError:
            return False

def create_date_ranges_from_tuples(date_tuples: List[Tuple[str, str]], 
                                  bearer_token: str, 
                                  org: str, 
                                  website: str, 
                                  environment: str = "production") -> List[Tuple[str, str]]:
    """
    Create optimized date ranges from a list of tuples.
    
    Args:
        date_tuples: List of (start_date, end_date) tuples
        bearer_token: API bearer token
        org: Organization ID
        website: Website identifier
        environment: Environment (production/sandbox)
        
    Returns:
        List of optimized (start_date, end_date) tuples
    """
    builder = DateRangeBuilder(bearer_token, org, website, environment)
    optimized_ranges = []
    
    for start_date, end_date in date_tuples:
        if builder.validate_date_range(start_date, end_date):
            ranges = builder.build_optimal_ranges(start_date, end_date)
            optimized_ranges.extend(ranges)
        else:
            logger.warning(f"Invalid date range: {start_date} to {end_date}")
    
    return optimized_ranges 