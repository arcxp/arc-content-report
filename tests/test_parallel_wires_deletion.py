#!/usr/bin/env python3
"""
Test script for parallel wires/stories deletion functionality
"""
import os
import sys
import tempfile
import csv
from typing import List

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wires_report.delete_wires import DeleteStories
from wires_report.delete_wires_parallel_processor import StoriesDeleteParallelProcessor


def create_test_csv(arc_ids: List[str], filename: str) -> str:
    """Create a test CSV file with arc IDs"""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for arc_id in arc_ids:
            writer.writerow([arc_id])
    return filename


def test_parallel_processor():
    """Test the parallel processor functionality"""
    print("Testing StoriesDeleteParallelProcessor...")
    
    # Mock authentication header
    arc_auth_header = {"Authorization": "Bearer test-token"}
    
    # Create processor
    processor = StoriesDeleteParallelProcessor(
        arc_auth_header=arc_auth_header,
        org="test-org",
        max_workers=2,
        rate_limit=5,
        dry_run=True  # Use dry run for testing
    )
    
    # Test data
    test_items = [
        "ABC123DEF456",
        "GHI789JKL012",
        "MNO345PQR678",
    ]
    
    # Mock delete function for testing
    def mock_delete_func(arc_id: str):
        import time
        time.sleep(0.1)  # Simulate API call
        return {
            "arc_id": arc_id,
            "status": "deleted",
            "response": 200
        }
    
    # Test parallel processing
    results = processor.process_stories_parallel(
        delete_func=mock_delete_func,
        story_items=test_items,
        chunk_size=2
    )
    
    print(f"Processed {len(results)} items")
    print(f"Statistics: {processor.get_statistics()}")
    
    # Verify results
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert all(r["status"] == "deleted" for r in results), "All items should be marked as deleted"
    
    print("✓ Parallel processor test passed!")


def test_delete_stories_integration():
    """Test the integration with DeleteStories class"""
    print("\nTesting DeleteStories integration...")
    
    # Create test CSV file
    test_items = [
        "ABC123DEF456",
        "GHI789JKL012",
        "MNO345PQR678",
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
        temp_csv = temp_file.name
        create_test_csv(test_items, temp_csv)
        
        try:
            # Create DeleteStories instance with dry run
            delete_processor = DeleteStories(
                org="test-org",
                arc_auth_header={"Authorization": "Bearer test-token"},
                wires_csv=temp_csv,
                dry_run=True,
                max_workers=2,
                batch_size=2,
                rate_limit=5
            )
            
            # Test the delete_stories method
            delete_processor.delete_stories()
            
            # Verify statistics
            stats = delete_processor.stats
            assert stats["total_stories_processed"] == 3, f"Expected 3 processed, got {stats['total_stories_processed']}"
            assert stats["stories_deleted"] == 3, f"Expected 3 deleted, got {stats['stories_deleted']}"
            
            print("✓ DeleteStories integration test passed!")
            
        finally:
            # Clean up
            os.unlink(temp_csv)


if __name__ == "__main__":
    print("Running parallel deletion tests...")
    
    try:
        test_parallel_processor()
        test_delete_stories_integration()
        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1) 