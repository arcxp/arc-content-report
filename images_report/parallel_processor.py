"""
Parallel Processor for Arc XP Images Report
Handles concurrent API calls for photo analysis and management
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional
import os
import utils
from ratelimit import limits, sleep_and_retry

logger = logging.getLogger(__name__)

class ImagesParallelProcessor:
    """Handles parallel processing of photos for API calls."""
    
    def __init__(self, arc_auth_header: Dict[str, str], org: str, max_workers: int = 8, rate_limit: int = 10):
        self.arc_auth_header = arc_auth_header
        self.org = org
        self.max_workers = max_workers
        self.rate_limit = rate_limit
        
    def process_photos_parallel(
        self, 
        func: Callable, 
        photo_ids: List[str], 
        chunk_size: int = 100,
        description: str = "Processing photos"
    ) -> List[Any]:
        """
        Process photos in parallel using ThreadPoolExecutor
        
        Args:
            func: Function to apply to each photo ID
            photo_ids: List of photo IDs to process
            chunk_size: Number of items to process in each batch
            description: Description for progress logging
            
        Returns:
            List of results from processing
        """
        logger.info(f"Starting parallel processing with {self.max_workers} workers")
        
        results = []
        total_items = len(photo_ids)
        
        # Process in chunks to avoid memory issues
        for i in range(0, total_items, chunk_size):
            chunk = photo_ids[i:i + chunk_size]
            logger.info(f"Processing chunk {i//chunk_size + 1}/{(total_items + chunk_size - 1)//chunk_size}")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks in the chunk
                future_to_item = {executor.submit(func, item): item for item in chunk}
                
                # Collect results as they complete
                for future in as_completed(future_to_item):
                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                    except Exception as e:
                        item = future_to_item[future]
                        logger.error(f"Error processing item {item}: {str(e)}")
        
        logger.info(f"Completed parallel processing. Processed {len(results)} items successfully")
        return results
    
    def process_lightboxes_parallel(
        self, 
        func: Callable, 
        lightbox_ids: List[str], 
        chunk_size: int = 50,
        description: str = "Processing lightboxes"
    ) -> List[Any]:
        """
        Process lightboxes in parallel using ThreadPoolExecutor
        
        Args:
            func: Function to apply to each lightbox ID
            lightbox_ids: List of lightbox IDs to process
            chunk_size: Number of items to process in each batch
            description: Description for progress logging
            
        Returns:
            List of results from processing
        """
        logger.info(f"Starting parallel lightbox processing with {self.max_workers} workers")
        
        results = []
        total_items = len(lightbox_ids)
        
        # Process in chunks to avoid memory issues
        for i in range(0, total_items, chunk_size):
            chunk = lightbox_ids[i:i + chunk_size]
            logger.info(f"Processing chunk {i//chunk_size + 1}/{(total_items + chunk_size - 1)//chunk_size}")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks in the chunk
                future_to_item = {executor.submit(func, item): item for item in chunk}
                
                # Collect results as they complete
                for future in as_completed(future_to_item):
                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                    except Exception as e:
                        item = future_to_item[future]
                        logger.error(f"Error processing lightbox {item}: {str(e)}")
        
        logger.info(f"Completed parallel lightbox processing. Processed {len(results)} items successfully")
        return results
    
    def benchmark_performance(
        self, 
        func: Callable, 
        items: List[str], 
        chunk_size: int = 100
    ) -> Dict[str, Any]:
        """
        Benchmark parallel processing performance.
        
        Args:
            func: Function to benchmark
            items: List of items to process
            chunk_size: Number of items per chunk
            
        Returns:
            Performance metrics dictionary
        """
        logger.info("Starting performance benchmark")
        
        # Process with current settings
        start_time = time.time()
        results = self.process_photos_parallel(func, items, chunk_size)
        end_time = time.time()
        
        processing_time = end_time - start_time
        items_per_second = len(results) / processing_time if processing_time > 0 else 0
        
        metrics = {
            "total_items": len(items),
            "processed_items": len(results),
            "processing_time_seconds": processing_time,
            "items_per_second": items_per_second,
            "max_workers": self.max_workers,
            "chunk_size": chunk_size
        }
        
        logger.info(f"Benchmark results: {metrics}")
        return metrics

def optimize_worker_count(
    func: Callable, 
    items: List[str], 
    arc_auth_header: Dict[str, str], 
    org: str,
    test_items: Optional[List[str]] = None
) -> int:
    """
    Find optimal number of workers for parallel processing.
    
    Args:
        func: Function to test
        items: List of items to process
        arc_auth_header: Authentication header
        org: Organization ID
        test_items: Optional subset of items for testing
        
    Returns:
        Optimal number of workers
    """
    logger.info("Finding optimal worker count")
    
    if test_items is None:
        test_items = items[:10]  # Test with first 10 items
    
    best_workers = 8
    best_performance = 0
    
    for workers in [1, 2, 4, 8, 12, 16]:
        processor = ImagesParallelProcessor(arc_auth_header, org, workers)
        metrics = processor.benchmark_performance(func, test_items)
        
        if metrics["items_per_second"] > best_performance:
            best_performance = metrics["items_per_second"]
            best_workers = workers
    
    logger.info(f"Optimal worker count: {best_workers} (performance: {best_performance:.2f} items/sec)")
    return best_workers 