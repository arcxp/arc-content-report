"""
Parallel Processor for Arc XP Redirects Search and Analysis
Handles concurrent API calls for fetching redirects by date ranges and consolidated CSV output
"""
import logging
import pandas as pd
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any
import os
import utils
from ratelimit import limits, sleep_and_retry

logger = logging.getLogger(__name__)

class RedirectsSearchParallelProcessor:
    """Handles parallel processing of date ranges for redirect search API calls."""
    
    def __init__(self, bearer_token: str, org: str, website: str, environment: str = "production", max_workers: int = 5):
        self.bearer_token = bearer_token
        self.org = org if environment == "production" else f"sandbox.{org}"
        self.website = website
        self.env = environment
        self.max_workers = max_workers
        self.arc_auth_header = {
            "Authorization": f"Bearer {self.bearer_token}", 
            "User-Agent": f"python-requests-{self.org}-script-arcxp"
        }
        
    @property
    def search_url(self) -> str:
        return f"https://api.{self.org}.arcpublishing.com/content/v4/search"
    
    @utils.log_api_call
    def fetch_redirects_for_range(self, date_range: Tuple[str, str]) -> List[Dict[str, Any]]:
        """
        Fetch redirects for a specific date range.
        
        Args:
            date_range: Tuple of (start_date, end_date)
            
        Returns:
            List of redirect data dictionaries
        """
        start_date, end_date = date_range
        logger.info(f"Fetching redirects for range: {start_date} to {end_date}")
        
        search_q = f"type:redirect AND created_date:[{start_date} TO {end_date}]"
        all_items = []
        from_next = 0
        
        while True:
            params = {
                "website": self.website,
                "track_total_hits": "true",
                "q": search_q,
                "size": "100",
                "from": from_next
            }
            
            try:
                @sleep_and_retry
                @limits(calls=20, period=60)
                def make_request():
                    response = requests.get(self.search_url, headers=self.arc_auth_header, params=params)
                    response.raise_for_status()
                    return response.json()
                
                data = make_request()
                
                if not data.get("content_elements"):
                    break
                
                # Process items
                for row in data["content_elements"]:
                    item = {
                        "identifier": row["_id"],
                        "canonical_url": row.get("canonical_url", ""),
                        "redirect_url": row.get("redirect_url", ""),
                        "created_date": row["created_date"],
                        "website": self.website,
                        "environment": self.env,
                        "check_404_or_200": ""
                    }
                    all_items.append(item)
                
                from_next += 100
                
                # Check if we've processed all items, and don't process if from_next param will go over 10k
                if from_next >= data.get("count", 0) or from_next >= 10000:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching data for {start_date} to {end_date}: {e}")
                break
        
        logger.info(f"Fetched {len(all_items)} redirects for {start_date} to {end_date}")
        return all_items
    
    @utils.timing_decorator
    def process_ranges_parallel(self, date_ranges: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """
        Process multiple date ranges in parallel.
        
        Args:
            date_ranges: List of (start_date, end_date) tuples
            
        Returns:
            Consolidated list of all redirect data
        """
        logger.info(f"Processing {len(date_ranges)} date ranges with {self.max_workers} workers")
        
        all_results = []
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_range = {
                executor.submit(self.fetch_redirects_for_range, date_range): date_range 
                for date_range in date_ranges
            }
            
            # Process completed tasks
            for future in as_completed(future_to_range):
                date_range = future_to_range[future]
                try:
                    result = future.result()
                    all_results.extend(result)
                    completed_count += 1
                    logger.info(f"Completed {completed_count}/{len(date_ranges)} ranges")
                except Exception as e:
                    logger.error(f"Error processing range {date_range}: {e}")
        
        logger.info(f"Parallel processing completed. Total items: {len(all_results)}")
        return all_results
    
    def export_to_csv(self, data: List[Dict[str, Any]], start_date: str, end_date: str, output_dir: str = "spreadsheets", output_prefix: str = "") -> str:
        """
        Export data to CSV with timestamp.
        
        Args:
            data: List of redirect data dictionaries
            start_date: Start date for filename
            end_date: End date for filename
            output_dir: Output directory
            
        Returns:
            Path to created CSV file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        if not data:
            logger.warning("No data to export")
            return ""
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Create filename
        filename = utils.create_output_filename(output_prefix, start_date, end_date, self.website)
        filepath = os.path.join(output_dir, filename)
        
        # Export to CSV
        df.to_csv(filepath, index=False)
        logger.info(f"Exported {len(data)} items to {filepath}")

        return filepath
    
    def benchmark_performance(self, date_ranges: List[Tuple[str, str]], output_dir: str = "spreadsheets") -> Dict[str, Any]:
        """
        Benchmark parallel processing performance.
        
        Args:
            date_ranges: List of date ranges to process
            output_dir: Output directory for CSV
            
        Returns:
            Performance metrics dictionary
        """
        logger.info("Starting performance benchmark")
        
        # Process with current settings
        start_time = time.time()
        results = self.process_ranges_parallel(date_ranges)
        end_time = time.time()
        
        processing_time = end_time - start_time
        items_per_second = len(results) / processing_time if processing_time > 0 else 0
        
        metrics = {
            "total_ranges": len(date_ranges),
            "total_items": len(results),
            "processing_time_seconds": processing_time,
            "items_per_second": items_per_second,
            "max_workers": self.max_workers
        }
        
        logger.info(f"Benchmark results: {metrics}")
        return metrics

def optimize_worker_count(date_ranges: List[Tuple[str, str]], bearer_token: str, org: str, website: str, environment: str = "production") -> int:
    """
    Find optimal number of workers for parallel processing.
    
    Args:
        date_ranges: List of date ranges to test
        bearer_token: API bearer token
        org: Organization ID
        website: Website identifier
        environment: Environment
        
    Returns:
        Optimal number of workers
    """
    logger.info("Finding optimal worker count")
    
    test_ranges = date_ranges[:3]  # Test with first 3 ranges
    best_workers = 5
    best_performance = 0
    
    for workers in [1, 3, 5, 8, 10]:
        processor = RedirectsSearchParallelProcessor(bearer_token, org, website, environment, workers)
        metrics = processor.benchmark_performance(test_ranges)
        
        if metrics["items_per_second"] > best_performance:
            best_performance = metrics["items_per_second"]
            best_workers = workers
    
    logger.info(f"Optimal worker count: {best_workers} (performance: {best_performance:.2f} items/sec)")
    return best_workers 