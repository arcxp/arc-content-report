"""
Asynchronous HTTP Status Checker for Arc XP Org Redirects Report
Efficiently checks redirect targets' HTTP statuses in parallel
"""
import logging
import asyncio
import aiohttp
from typing import List, Dict, Any, Tuple
import utils

logger = logging.getLogger(__name__)

class AsyncStatusChecker:
    """Handles asynchronous HTTP status checking for redirect URLs."""
    
    def __init__(self, website_domain: str, max_concurrent: int = 100, timeout: int = 30):
        self.website_domain = website_domain.rstrip('/')
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        timeout_config = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            timeout=timeout_config,
            headers={'User-Agent': 'arc-identify-redirects-async'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def check_single_status(self, url: str) -> Tuple[str, Any]:
        """
        Check HTTP status for a single URL.
        
        Args:
            url: URL to check
            
        Returns:
            Tuple of (url, status_code)
        """
        full_url = f"{self.website_domain}{url}" if not url.startswith('http') else url
        
        try:
            if self.session:
                async with self.session.get(full_url, allow_redirects=False) as response:
                    return url, response.status
            else:
                return url, "error"
        except asyncio.TimeoutError:
            logger.warning(f"Timeout checking {full_url}")
            return url, "timeout"
        except Exception as e:
            logger.warning(f"Error checking {full_url}: {e}")
            return url, "error"
    
    async def check_urls_batch(self, urls: List[str]) -> List[Tuple[str, int]]:
        """
        Check HTTP status for a batch of URLs concurrently.
        
        Args:
            urls: List of URLs to check
            
        Returns:
            List of (url, status_code) tuples
        """
        logger.info(f"Checking {len(urls)} URLs in batch")
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def check_with_semaphore(url: str) -> Tuple[str, int]:
            async with semaphore:
                return await self.check_single_status(url)
        
        # Execute all checks concurrently
        tasks = [check_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
                processed_results.append(("unknown", "error"))
            else:
                processed_results.append(result)
        
        logger.info(f"Completed batch check for {len(urls)} URLs")
        return processed_results
    
    @utils.timing_decorator
    async def check_all_urls(self, urls: List[str], batch_size: int = 100) -> Dict[str, int]:
        """
        Check HTTP status for all URLs in batches.
        
        Args:
            urls: List of URLs to check
            batch_size: Number of URLs to process in each batch
            
        Returns:
            Dictionary mapping URLs to status codes
        """
        logger.info(f"Starting status check for {len(urls)} URLs")
        
        # Remove duplicates while preserving order
        unique_urls = list(dict.fromkeys(urls))
        logger.info(f"Removed duplicates: {len(urls)} -> {len(unique_urls)} URLs")
        
        # Split into batches
        url_batches = utils.chunk_list(unique_urls, batch_size)
        logger.info(f"Split into {len(url_batches)} batches of {batch_size}")
        
        all_results = []
        
        for i, batch in enumerate(url_batches, 1):
            logger.info(f"Processing batch {i}/{len(url_batches)} ({len(batch)} URLs)")
            batch_results = await self.check_urls_batch(batch)
            all_results.extend(batch_results)
        
        # Convert to dictionary
        status_dict = dict(all_results)
        
        # Log summary
        status_counts = {}
        for status in status_dict.values():
            status_counts[status] = status_counts.get(status, 0) + 1
        
        logger.info(f"Status check completed. Summary: {status_counts}")
        return status_dict

def update_dataframe_with_statuses(data: List[Dict[str, Any]], status_dict: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    Update dataframe with HTTP status codes.
    
    Args:
        data: List of redirect data dictionaries
        status_dict: Dictionary mapping URLs to status codes
        
    Returns:
        Updated data with status codes
    """
    logger.info("Updating data with HTTP status codes")
    
    updated_data = []
    for item in data:
        canonical_url = item.get("canonical_url", "")
        status_code = status_dict.get(canonical_url, "")
        
        updated_item = item.copy()
        updated_item["check_404_or_200"] = str(status_code)
        updated_data.append(updated_item)
    
    logger.info(f"Updated {len(updated_data)} items with status codes")
    return updated_data

async def check_redirect_statuses_async(data: List[Dict[str, Any]], website_domain: str) -> List[Dict[str, Any]]:
    """
    Main function to check redirect statuses asynchronously.
    
    Args:
        data: List of redirect data dictionaries
        website_domain: Website domain for URL construction
        
    Returns:
        Updated data with HTTP status codes
    """
    logger.info("Starting asynchronous status checking")
    
    # Extract unique URLs
    urls = [item.get("canonical_url", "") for item in data if item.get("canonical_url")]
    urls = [url for url in urls if url]  # Remove empty URLs
    
    if not urls:
        logger.warning("No URLs to check")
        return data
    
    # Check statuses
    async with AsyncStatusChecker(website_domain) as checker:
        status_dict = await checker.check_all_urls(urls)
    
    # Update data
    updated_data = update_dataframe_with_statuses(data, status_dict)
    
    return updated_data

def check_redirect_statuses_sync(data: List[Dict[str, Any]], website_domain: str) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for async status checking.
    
    Args:
        data: List of redirect data dictionaries
        website_domain: Website domain for URL construction
        
    Returns:
        Updated data with HTTP status codes
    """
    logger.info("Running synchronous wrapper for async status checking")
    return asyncio.run(check_redirect_statuses_async(data, website_domain)) 