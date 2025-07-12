#!/usr/bin/env python3
"""
Test script for the delete_or_expire_photos functionality.
This script tests the photo deletion and expiration functionality without making actual API calls.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import csv
from typing import List, Dict, Any

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from images_report.delete_or_expire_photos import DeleteDefunctPhotos


class TestDeleteDefunctPhotos(unittest.TestCase):
    """Test cases for the DeleteDefunctPhotos class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.org = "testorg"
        self.arc_auth_header = {"Authorization": "Bearer test_token"}
        self.processor = DeleteDefunctPhotos(
            org=self.org,
            arc_auth_header=self.arc_auth_header,
            max_workers=2,
            batch_size=10,
            rate_limit=5
        )
    
    def test_initialization(self):
        """Test that the processor initializes correctly"""
        self.assertEqual(self.processor.org, self.org)
        self.assertEqual(self.processor.arc_auth_header, self.arc_auth_header)
        self.assertEqual(self.processor.max_workers, 2)
        self.assertEqual(self.processor.batch_size, 10)
        self.assertFalse(self.processor.hard_delete)
        self.assertEqual(self.processor.stats["total_photos_processed"], 0)
        self.assertEqual(self.processor.stats["photos_deleted"], 0)
        self.assertEqual(self.processor.stats["photos_expired"], 0)
        self.assertEqual(self.processor.stats["photos_failed"], 0)
    
    def test_initialization_with_hard_delete(self):
        """Test initialization with hard delete enabled"""
        processor = DeleteDefunctPhotos(
            org=self.org,
            arc_auth_header=self.arc_auth_header,
            hard_delete=True
        )
        self.assertTrue(processor.hard_delete)
    
    def test_get_preserved_photo_ids(self):
        """Test getting preserved photo IDs from CSV"""
        # Create a temporary CSV file with the expected naming pattern
        temp_dir = tempfile.gettempdir()
        temp_csv = os.path.join(temp_dir, "photo_ids_to_delete_test.csv")
        
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ans_id'])
            writer.writerow(['photo1'])
            writer.writerow(['photo2'])
        
        try:
            # Create the corresponding preserved CSV file
            preserved_csv = temp_csv.replace("photo_ids_to_delete_", "preserved_photo_ids_")
            with open(preserved_csv, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['ans_id'])
                writer.writerow(['photo1'])
            
            # Test getting preserved IDs
            preserved_ids = self.processor.get_preserved_photo_ids(temp_csv)
            self.assertIn('photo1', preserved_ids)
            self.assertNotIn('photo2', preserved_ids)
            
        finally:
            # Clean up temporary files
            if os.path.exists(temp_csv):
                os.unlink(temp_csv)
            if os.path.exists(preserved_csv):
                os.unlink(preserved_csv)
    
    def test_get_preserved_photo_ids_no_file(self):
        """Test getting preserved photo IDs when file doesn't exist"""
        temp_dir = tempfile.gettempdir()
        temp_csv = os.path.join(temp_dir, "photo_ids_to_delete_test_no_preserved.csv")
        
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ans_id'])
            writer.writerow(['photo1'])
        
        try:
            # Test when preserved file doesn't exist
            preserved_ids = self.processor.get_preserved_photo_ids(temp_csv)
            self.assertEqual(len(preserved_ids), 0)
            
        finally:
            if os.path.exists(temp_csv):
                os.unlink(temp_csv)
    
    @patch('images_report.delete_or_expire_photos.requests.delete')
    def test_delete_single_photo_success(self, mock_delete):
        """Test successful photo deletion"""
        # Mock successful response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        
        result = self.processor.delete_single_photo("test_photo_id")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "deleted")
        self.assertEqual(result["photo_id"], "test_photo_id")
        self.assertEqual(self.processor.stats["photos_deleted"], 1)
        self.assertEqual(self.processor.stats["api_calls"], 1)
    
    @patch('images_report.delete_or_expire_photos.requests.delete')
    def test_delete_single_photo_failure(self, mock_delete):
        """Test failed photo deletion"""
        # Mock failed response
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "Photo not found"
        mock_delete.return_value = mock_response
        
        result = self.processor.delete_single_photo("test_photo_id")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["photo_id"], "test_photo_id")
        self.assertEqual(self.processor.stats["photos_failed"], 1)
        self.assertEqual(self.processor.stats["api_calls"], 1)
    
    @patch('images_report.delete_or_expire_photos.requests.get')
    @patch('images_report.delete_or_expire_photos.requests.put')
    def test_expire_single_photo_success(self, mock_put, mock_get):
        """Test successful photo expiration"""
        # Mock successful GET response
        mock_get_response = Mock()
        mock_get_response.ok = True
        mock_get_response.json.return_value = {
            "additional_properties": {},
            "published": True
        }
        mock_get.return_value = mock_get_response
        
        # Mock successful PUT response
        mock_put_response = Mock()
        mock_put_response.ok = True
        mock_put_response.status_code = 200
        mock_put.return_value = mock_put_response
        
        result = self.processor.expire_single_photo("test_photo_id")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "expired")
        self.assertEqual(result["photo_id"], "test_photo_id")
        self.assertEqual(self.processor.stats["photos_expired"], 1)
        self.assertEqual(self.processor.stats["api_calls"], 2)
    
    @patch('images_report.delete_or_expire_photos.requests.get')
    def test_expire_single_photo_get_failure(self, mock_get):
        """Test photo expiration when GET fails"""
        # Mock failed GET response
        mock_get_response = Mock()
        mock_get_response.ok = False
        mock_get_response.status_code = 404
        mock_get_response.text = "Photo not found"
        mock_get.return_value = mock_get_response
        
        result = self.processor.expire_single_photo("test_photo_id")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["photo_id"], "test_photo_id")
        self.assertEqual(self.processor.stats["photos_failed"], 1)
        self.assertEqual(self.processor.stats["api_calls"], 1)
    
    def test_process_photo_hard_delete(self):
        """Test photo processing with hard delete enabled"""
        self.processor.hard_delete = True
        
        with patch.object(self.processor, 'delete_single_photo') as mock_delete:
            mock_delete.return_value = {"status": "deleted"}
            
            result = self.processor.process_photo("test_photo_id")
            
            mock_delete.assert_called_once_with("test_photo_id")
            self.assertEqual(result["status"], "deleted")
    
    def test_process_photo_expire(self):
        """Test photo processing with expiration (default)"""
        with patch.object(self.processor, 'expire_single_photo') as mock_expire:
            mock_expire.return_value = {"status": "expired"}
            
            result = self.processor.process_photo("test_photo_id")
            
            mock_expire.assert_called_once_with("test_photo_id")
            self.assertEqual(result["status"], "expired")
    
    def test_print_statistics(self):
        """Test statistics printing"""
        # Set up some test statistics
        self.processor.stats.update({
            "total_photos_processed": 100,
            "photos_deleted": 50,
            "photos_expired": 30,
            "photos_failed": 20,
            "api_calls": 150,
            "start_time": 0  # Set to 0 for predictable duration
        })
        
        # Capture stdout to test the output
        with patch('sys.stdout') as mock_stdout:
            self.processor.print_statistics()
            
            # Verify that print was called (we can't easily test the exact output)
            self.assertTrue(mock_stdout.write.called or mock_stdout.print.called)


class TestDeleteDefunctPhotosIntegration(unittest.TestCase):
    """Integration tests for the DeleteDefunctPhotos class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.org = "testorg"
        self.arc_auth_header = {"Authorization": "Bearer test_token"}
    
    @patch('images_report.delete_or_expire_photos.ImagesParallelProcessor')
    def test_delete_arcids_with_csv(self, mock_parallel_processor_class):
        """Test deleting photos from CSV file"""
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(['photo1'])
            writer.writerow(['photo2'])
            writer.writerow(['photo3'])
            temp_csv = f.name
        
        try:
            processor = DeleteDefunctPhotos(
                org=self.org,
                arc_auth_header=self.arc_auth_header,
                images_csv=temp_csv
            )
            
            # Mock the ImagesParallelProcessor instance
            mock_processor_instance = Mock()
            mock_processor_instance.process_photos_parallel.return_value = [
                {"photo_id": "photo1", "status": "deleted"},
                {"photo_id": "photo2", "status": "failed"},
                {"photo_id": "photo3", "status": "deleted"}
            ]
            mock_parallel_processor_class.return_value = mock_processor_instance
            
            # Mock the get_preserved_photo_ids method
            with patch.object(processor, 'get_preserved_photo_ids', return_value=set()):
                processor.delete_arcids()
            
            # Verify that ImagesParallelProcessor was instantiated and process_photos_parallel was called
            mock_parallel_processor_class.assert_called_once()
            mock_processor_instance.process_photos_parallel.assert_called_once()
            
            # Verify statistics
            self.assertEqual(processor.stats["total_photos_processed"], 3)
            
        finally:
            if os.path.exists(temp_csv):
                os.unlink(temp_csv)
    
    def test_delete_arcids_single_photo(self):
        """Test deleting a single photo"""
        processor = DeleteDefunctPhotos(
            org=self.org,
            arc_auth_header=self.arc_auth_header,
            image_arc_id="test_photo_id"
        )
        
        with patch.object(processor, 'process_photo') as mock_process:
            mock_process.return_value = {"photo_id": "test_photo_id", "status": "deleted"}
            
            processor.delete_arcids()
            
            mock_process.assert_called_once_with("test_photo_id")
            self.assertEqual(processor.stats["total_photos_processed"], 1)
    
    def test_delete_arcids_no_input(self):
        """Test deleting photos with no input provided"""
        processor = DeleteDefunctPhotos(
            org=self.org,
            arc_auth_header=self.arc_auth_header
        )
        
        # Should not raise an exception, but should log an error
        with patch.object(processor.logger, 'error') as mock_error:
            processor.delete_arcids()
            mock_error.assert_called()


def main():
    """Run the test suite"""
    print("=" * 60)
    print("Testing delete_or_expire_photos functionality")
    print("=" * 60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestDeleteDefunctPhotos))
    suite.addTests(loader.loadTestsFromTestCase(TestDeleteDefunctPhotosIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("🎉 All tests passed!")
        print("The delete_or_expire_photos functionality is working correctly.")
    else:
        print("❌ Some tests failed.")
        print("Please review the test output above.")
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main()) 