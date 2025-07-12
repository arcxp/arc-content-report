#!/usr/bin/env python3
"""
Test script to verify that the images_report module works correctly.
This script tests imports and basic functionality without making API calls.
"""

import sys
import os
import importlib.util
from typing import List, Dict, Any

def test_imports() -> bool:
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    modules_to_test = [
        "images_report.create_lightbox_cache",
        "images_report.published_photo_analysis",
        "images_report.delete_or_expire_photos"
    ]
    
    failed_imports = []
    
    for module_name in modules_to_test:
        try:
            # Try to import the module
            module = importlib.import_module(module_name)
            print(f"✓ Successfully imported {module_name}")
        except Exception as e:
            print(f"✗ Failed to import {module_name}: {str(e)}")
            failed_imports.append(module_name)
    
    if failed_imports:
        print(f"\nFailed imports: {failed_imports}")
        return False
    else:
        print("\n✓ All imports successful!")
        return True

def test_utils_functions() -> bool:
    """Test utility functions"""
    print("\nTesting utility functions...")
    
    try:
        from utils import (
            setup_logging,
            benchmark,
            parallel_process,
            RateLimiter,
            get_csv_path,
            get_db_path,
            format_timestamp,
            format_duration,
            PerformanceBenchmark
        )
        
        # Test basic functions
        csv_path = get_csv_path("test.csv")
        db_path = get_db_path("test.db")
        
        print(f"✓ CSV path: {csv_path}")
        print(f"✓ DB path: {db_path}")
        
        # Test formatting functions
        timestamp_ms = 1577854800000
        formatted_time = format_timestamp(timestamp_ms)
        print(f"✓ Timestamp formatting: {formatted_time}")
        
        duration = format_duration(125.5)
        print(f"✓ Duration formatting: {duration}")
        
        # Test rate limiter
        rate_limiter = RateLimiter(10)
        print("✓ Rate limiter created")
        
        # Test performance benchmark
        with PerformanceBenchmark("Test Benchmark"):
            pass
        print("✓ Performance benchmark works")
        
        return True
        
    except Exception as e:
        print(f"✗ Utility functions test failed: {str(e)}")
        return False

def test_directory_structure() -> bool:
    """Test that required directories exist or can be created"""
    print("\nTesting directory structure...")
    
    directories = ["logs", "spreadsheets", "databases"]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            if os.path.exists(directory):
                print(f"✓ Directory {directory} exists")
            else:
                print(f"✗ Directory {directory} could not be created")
                return False
        except Exception as e:
            print(f"✗ Error with directory {directory}: {str(e)}")
            return False
    
    return True

def test_requirements() -> bool:
    """Test that required packages are installed"""
    print("\nTesting required packages...")

    # python-decouple might fail even if it is properly install
    required_packages = [
        "requests",
        "jmespath", 
        "tqdm",
        "arrow",
        "psutil",
        "decouple"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is installed")
        except ImportError:
            print(f"✗ {package} is missing")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nMissing packages: {missing_packages}")
        print("Install them with: pip install -r requirements.txt")
        return False
    else:
        print("\n✓ All required packages are installed!")
        return True

def test_images_report_classes() -> bool:
    """Test that the main classes can be instantiated"""
    print("\nTesting images_report classes...")
    
    try:
        # Test DeleteDefunctPhotos class
        from images_report.delete_or_expire_photos import DeleteDefunctPhotos
        print("✓ DeleteDefunctPhotos class imported")
        
        # Test CombinedPhotoAnalysis class
        from images_report.published_photo_analysis import CombinedPhotoAnalysis
        print("✓ CombinedPhotoAnalysis class imported")
        
        # Test LightboxCache class
        from images_report.create_lightbox_cache import LightboxCache
        print("✓ LightboxCache class imported")
        
        return True
        
    except Exception as e:
        print(f"✗ Class import test failed: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print(f"Testing images_report module")
    print("=" * 50)
    
    tests = [
        ("Directory Structure", test_directory_structure),
        ("Required Packages", test_requirements),
        ("Utility Functions", test_utils_functions),
        ("Module Imports", test_imports),
        ("Class Imports", test_images_report_classes)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        if test_func():
            passed += 1
            print(f"✓ {test_name} PASSED")
        else:
            print(f"✗ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The images_report module is ready to use.")
        print("\nNext steps:")
        print("1. Set up your virtual environment: python3 -m venv arc-content-report")
        print("2. Activate it: source arc-content-report/bin/activate")
        print("3. Install dependencies: pip install -r requirements.txt")
        print("4. Create .env file with your configuration")
        print("5. Run the scripts using the shell scripts in images_report/")
    else:
        print("❌ Some tests failed. Please fix the issues before proceeding.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 