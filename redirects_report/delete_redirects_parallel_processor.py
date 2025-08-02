"""
Parallel Processor for Arc XP Redirects Deletion
Handles concurrent API calls for redirect deletion with rate limiting and statistics
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional, Tuple
import os
import utils
from ratelimit import limits, sleep_and_retry

logger = logging.getLogger(__name__)

class RedirectsDeleteParallelProcessor:
    """Handles parallel processing of redirect deletions with rate limiting and statistics."""
    
    def __init__(
        self, 
        arc_auth_header: Dict[str, str], 
        org: str, 
        max_workers: int = 8, 
        rate_limit: int = 4,
        dry_run: bool = False
    ):
        self.arc_auth_header = arc_auth_header
        self.org = org
        self.max_workers = max_workers
        self.rate_limit = rate_limit
        self.dry_run = dry_run
        
        # Statistics tracking
        self.stats = {
            "total_redirects_processed": 0,
            "redirects_deleted": 0,
            "redirects_failed": 0,
            "api_calls": 0,
            "start_time": time.time()
        }
        
    def process_redirects_parallel(
        self, 
        delete_func: Callable, 
        redirect_items: List[Tuple[str, str]], 
        chunk_size: int = 100,
        description: str = "Deleting redirects"
    ) -> List[Dict[str, Any]]:
        """
        Process redirect deletions in parallel using ThreadPoolExecutor
        
        Args:
            delete_func: Function to apply to each redirect item (should take redirect_url, redirect_website)
            redirect_items: List of (redirect_url, redirect_website) tuples to process
            chunk_size: Number of items to process in each batch
            description: Description for progress logging
            
        Returns:
            List of results from processing
        """
        logger.info(f"Starting parallel redirect deletion with {self.max_workers} workers")
        logger.info(f"Total redirects to process: {len(redirect_items)}")
        
        results = []
        total_items = len(redirect_items)
        self.stats["total_redirects_processed"] = total_items
        
        # Process in chunks to avoid memory issues and provide progress updates
        for i in range(0, total_items, chunk_size):
            chunk = redirect_items[i:i + chunk_size]
            chunk_num = i//chunk_size + 1
            total_chunks = (total_items + chunk_size - 1)//chunk_size
            
            logger.info(f"Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} items)")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks in the chunk
                future_to_item = {executor.submit(delete_func, item[0], item[1]): item for item in chunk}
                
                # Collect results as they complete
                for future in as_completed(future_to_item):
                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                            # Update statistics based on result
                            if result.get("status") == "deleted":
                                self.stats["redirects_deleted"] += 1
                            elif result.get("status") in ["failed", "error"]:
                                self.stats["redirects_failed"] += 1
                    except Exception as e:
                        item = future_to_item[future]
                        logger.error(f"Error processing redirect {item}: {str(e)}")
                        self.stats["redirects_failed"] += 1
                        results.append({
                            "redirect_url": item[0],
                            "redirect_website": item[1],
                            "status": "error",
                            "error": str(e)
                        })
            
            # Log progress after each chunk
            processed_so_far = len(results)
            logger.info(f"Completed chunk {chunk_num}/{total_chunks}. "
                       f"Progress: {processed_so_far}/{total_items} items processed")
        
        # Log final statistics
        processing_time = time.time() - self.stats["start_time"]
        logger.info(f"Completed parallel redirect deletion in {processing_time:.2f} seconds")
        logger.info(f"Final stats: {self.stats['redirects_deleted']} deleted, "
                   f"{self.stats['redirects_failed']} failed, "
                   f"{self.stats['api_calls']} API calls")
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        processing_time = time.time() - self.stats["start_time"]
        return {
            **self.stats,
            "processing_time_seconds": processing_time,
            "success_rate": (self.stats["redirects_deleted"] / self.stats["total_redirects_processed"] * 100) 
                           if self.stats["total_redirects_processed"] > 0 else 0
        }
    
    def benchmark_performance(
        self, 
        delete_func: Callable, 
        redirect_items: List[Tuple[str, str]], 
        chunk_size: int = 100
    ) -> Dict[str, Any]:
        """
        Benchmark parallel processing performance.
        
        Args:
            delete_func: Function to benchmark
            redirect_items: List of redirect items to process
            chunk_size: Number of items per chunk
            
        Returns:
            Performance metrics dictionary
        """
        logger.info("Starting performance benchmark")
        
        # Reset stats for benchmark
        self.stats = {
            "total_redirects_processed": 0,
            "redirects_deleted": 0,
            "redirects_failed": 0,
            "api_calls": 0,
            "start_time": time.time()
        }
        
        # Process with current settings
        results = self.process_redirects_parallel(delete_func, redirect_items, chunk_size)
        
        # Calculate metrics
        processing_time = time.time() - self.stats["start_time"]
        items_per_second = len(results) / processing_time if processing_time > 0 else 0
        
        metrics = {
            "total_items": len(redirect_items),
            "processed_items": len(results),
            "processing_time_seconds": processing_time,
            "items_per_second": items_per_second,
            "max_workers": self.max_workers,
            "chunk_size": chunk_size,
            "success_rate": self.stats["redirects_deleted"] / len(redirect_items) * 100 if redirect_items else 0,
            "api_calls": self.stats["api_calls"]
        }
        
        logger.info(f"Benchmark results: {metrics}")
        return metrics

def optimize_worker_count(
    delete_func: Callable, 
    redirect_items: List[Tuple[str, str]], 
    arc_auth_header: Dict[str, str], 
    org: str,
    test_items: Optional[List[Tuple[str, str]]] = None,
    dry_run: bool = False
) -> int:
    """
    Find optimal number of workers for parallel processing.
    
    Args:
        delete_func: Function to test
        redirect_items: List of redirect items to process
        arc_auth_header: Authentication header
        org: Organization ID
        test_items: Optional subset of items for testing
        dry_run: Whether to run in dry-run mode
        
    Returns:
        Optimal number of workers
    """
    logger.info("Finding optimal worker count")
    
    if test_items is None:
        test_items = redirect_items[:10]  # Test with first 10 items
    
    best_workers = 8
    best_performance = 0
    
    for workers in [1, 2, 4, 8, 12, 16]:
        processor = RedirectsDeleteParallelProcessor(
            arc_auth_header, org, workers, dry_run=dry_run
        )
        metrics = processor.benchmark_performance(delete_func, test_items)
        
        if metrics["items_per_second"] > best_performance:
            best_performance = metrics["items_per_second"]
            best_workers = workers
    
    logger.info(f"Optimal worker count: {best_workers} (performance: {best_performance:.2f} items/sec)")
    return best_workers 