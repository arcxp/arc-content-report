#!/usr/bin/env python3
"""
Test script for parallel redirect deletion functionality
"""
import os
import sys
import tempfile
import csv
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redirects_report.delete_redirects import DeleteRedirects
from redirects_report.delete_redirects_parallel_processor import RedirectsDeleteParallelProcessor


def create_test_csv(redirect_items: List[Tuple[str, str]], filename: str) -> str:
    """Create a test CSV file with redirect data"""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for redirect_url, website in redirect_items:
            writer.writerow([redirect_url, website])
    return filename


def test_parallel_processor():
    """Test the parallel processor functionality"""
    print("Testing RedirectsDeleteParallelProcessor...")
    
    # Mock authentication header
    arc_auth_header = {"Authorization": "Bearer test-token"}
    
    # Create processor
    processor = RedirectsDeleteParallelProcessor(
        arc_auth_header=arc_auth_header,
        org="test-org",
        max_workers=2,
        rate_limit=5,
        dry_run=True  # Use dry run for testing
    )
    
    # Test data
    test_items = [
        ("/test/redirect1", "test-website"),
        ("/test/redirect2", "test-website"),
        ("/test/redirect3", "test-website"),
    ]
    
    # Mock delete function for testing
    def mock_delete_func(redirect_url: str, redirect_website: str):
        import time
        time.sleep(0.1)  # Simulate API call
        return {
            "redirect_url": redirect_url,
            "redirect_website": redirect_website,
            "status": "deleted",
            "response": 200
        }
    
    # Test parallel processing
    results = processor.process_redirects_parallel(
        delete_func=mock_delete_func,
        redirect_items=test_items,
        chunk_size=2
    )
    
    print(f"Processed {len(results)} items")
    print(f"Statistics: {processor.get_statistics()}")
    
    # Verify results
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert all(r["status"] == "deleted" for r in results), "All items should be marked as deleted"
    
    print("✓ Parallel processor test passed!")


def test_delete_redirects_integration():
    """Test the integration with DeleteRedirects class"""
    print("\nTesting DeleteRedirects integration...")
    
    # Create test CSV file
    test_items = [
        ("/test/redirect1", "test-website"),
        ("/test/redirect2", "test-website"),
        ("/test/redirect3", "test-website"),
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
        temp_csv = temp_file.name
        create_test_csv(test_items, temp_csv)
        
        try:
            # Create DeleteRedirects instance with dry run
            delete_processor = DeleteRedirects(
                org="test-org",
                arc_auth_header={"Authorization": "Bearer test-token"},
                redirects_csv=temp_csv,
                dry_run=True,
                max_workers=2,
                batch_size=2,
                rate_limit=5
            )
            
            # Test the delete_redirects method
            delete_processor.delete_redirects()
            
            # Verify statistics
            stats = delete_processor.stats
            assert stats["total_redirects_processed"] == 3, f"Expected 3 processed, got {stats['total_redirects_processed']}"
            assert stats["redirects_deleted"] == 3, f"Expected 3 deleted, got {stats['redirects_deleted']}"
            
            print("✓ DeleteRedirects integration test passed!")
            
        finally:
            # Clean up
            os.unlink(temp_csv)


if __name__ == "__main__":
    print("Running parallel deletion tests...")
    
    try:
        test_parallel_processor()
        test_delete_redirects_integration()
        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1) 