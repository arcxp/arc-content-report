"""
Parallel Processor for Arc XP Wires/Stories Deletion
Handles concurrent API calls for story deletion with rate limiting and statistics
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional
import os
import utils
from ratelimit import limits, sleep_and_retry

logger = logging.getLogger(__name__)

class StoriesDeleteParallelProcessor:
    """Handles parallel processing of story deletions with rate limiting and statistics."""
    
    def __init__(
        self, 
        arc_auth_header: Dict[str, str], 
        org: str, 
        max_workers: int = 8, 
        rate_limit: int = 10,
        dry_run: bool = False
    ):
        self.arc_auth_header = arc_auth_header
        self.org = org
        self.max_workers = max_workers
        self.rate_limit = rate_limit
        self.dry_run = dry_run
        
        # Statistics tracking
        self.stats = {
            "total_stories_processed": 0,
            "stories_deleted": 0,
            "stories_failed": 0,
            "api_calls": 0,
            "start_time": time.time()
        }
        
    def process_stories_parallel(
        self, 
        delete_func: Callable, 
        story_items: List[str], 
        chunk_size: int = 100,
        description: str = "Deleting stories"
    ) -> List[Dict[str, Any]]:
        """
        Process story deletions in parallel using ThreadPoolExecutor
        
        Args:
            delete_func: Function to apply to each story item (should take arc_id)
            story_items: List of arc_id strings to process
            chunk_size: Number of items to process in each batch
            description: Description for progress logging
            
        Returns:
            List of results from processing
        """
        logger.info(f"Starting parallel story deletion with {self.max_workers} workers")
        logger.info(f"Total stories to process: {len(story_items)}")
        
        results = []
        total_items = len(story_items)
        self.stats["total_stories_processed"] = total_items
        
        # Process in chunks to avoid memory issues and provide progress updates
        for i in range(0, total_items, chunk_size):
            chunk = story_items[i:i + chunk_size]
            chunk_num = i//chunk_size + 1
            total_chunks = (total_items + chunk_size - 1)//chunk_size
            
            logger.info(f"Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} items)")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks in the chunk
                future_to_item = {executor.submit(delete_func, item): item for item in chunk}
                
                # Collect results as they complete
                for future in as_completed(future_to_item):
                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                            # Update statistics based on result
                            if result.get("status") == "deleted":
                                self.stats["stories_deleted"] += 1
                            elif result.get("status") in ["failed", "error"]:
                                self.stats["stories_failed"] += 1
                    except Exception as e:
                        item = future_to_item[future]
                        logger.error(f"Error processing story {item}: {str(e)}")
                        self.stats["stories_failed"] += 1
                        results.append({
                            "arc_id": item,
                            "status": "error",
                            "error": str(e)
                        })
            
            # Log progress after each chunk
            processed_so_far = len(results)
            logger.info(f"Completed chunk {chunk_num}/{total_chunks}. "
                       f"Progress: {processed_so_far}/{total_items} items processed")
        
        # Log final statistics
        processing_time = time.time() - self.stats["start_time"]
        logger.info(f"Completed parallel story deletion in {processing_time:.2f} seconds")
        logger.info(f"Final stats: {self.stats['stories_deleted']} deleted, "
                   f"{self.stats['stories_failed']} failed, "
                   f"{self.stats['api_calls']} API calls")
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        processing_time = time.time() - self.stats["start_time"]
        return {
            **self.stats,
            "processing_time_seconds": processing_time,
            "success_rate": (self.stats["stories_deleted"] / self.stats["total_stories_processed"] * 100) 
                           if self.stats["total_stories_processed"] > 0 else 0
        }
    
    def benchmark_performance(
        self, 
        delete_func: Callable, 
        story_items: List[str], 
        chunk_size: int = 100
    ) -> Dict[str, Any]:
        """
        Benchmark parallel processing performance.
        
        Args:
            delete_func: Function to benchmark
            story_items: List of story items to process
            chunk_size: Number of items per chunk
            
        Returns:
            Performance metrics dictionary
        """
        logger.info("Starting performance benchmark")
        
        # Reset stats for benchmark
        self.stats = {
            "total_stories_processed": 0,
            "stories_deleted": 0,
            "stories_failed": 0,
            "api_calls": 0,
            "start_time": time.time()
        }
        
        # Process with current settings
        results = self.process_stories_parallel(delete_func, story_items, chunk_size)
        
        # Calculate metrics
        processing_time = time.time() - self.stats["start_time"]
        items_per_second = len(results) / processing_time if processing_time > 0 else 0
        
        metrics = {
            "total_items": len(story_items),
            "processed_items": len(results),
            "processing_time_seconds": processing_time,
            "items_per_second": items_per_second,
            "max_workers": self.max_workers,
            "chunk_size": chunk_size,
            "success_rate": self.stats["stories_deleted"] / len(story_items) * 100 if story_items else 0,
            "api_calls": self.stats["api_calls"]
        }
        
        logger.info(f"Benchmark results: {metrics}")
        return metrics

def optimize_worker_count(
    delete_func: Callable, 
    story_items: List[str], 
    arc_auth_header: Dict[str, str], 
    org: str,
    test_items: Optional[List[str]] = None,
    dry_run: bool = False
) -> int:
    """
    Find optimal number of workers for parallel processing.
    
    Args:
        delete_func: Function to test
        story_items: List of story items to process
        arc_auth_header: Authentication header
        org: Organization ID
        test_items: Optional subset of items for testing
        dry_run: Whether to run in dry-run mode
        
    Returns:
        Optimal number of workers
    """
    logger.info("Finding optimal worker count")
    
    if test_items is None:
        test_items = story_items[:10]  # Test with first 10 items
    
    best_workers = 8
    best_performance = 0
    
    for workers in [1, 2, 4, 8, 12, 16]:
        processor = StoriesDeleteParallelProcessor(
            arc_auth_header, org, workers, dry_run=dry_run
        )
        metrics = processor.benchmark_performance(delete_func, test_items)
        
        if metrics["items_per_second"] > best_performance:
            best_performance = metrics["items_per_second"]
            best_workers = workers
    
    logger.info(f"Optimal worker count: {best_workers} (performance: {best_performance:.2f} items/sec)")
    return best_workers 