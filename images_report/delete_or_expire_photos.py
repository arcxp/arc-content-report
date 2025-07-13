import argparse
import csv
import os
import pprint
import time
from typing import List, Dict, Any, Optional

import requests

from utils import (
    setup_logging, 
    benchmark, 
    RateLimiter, 
    get_csv_path,
    format_duration,
    PerformanceBenchmark
)
from .parallel_processor import ImagesParallelProcessor

PHOTO_API_URL = "https://api.{}.arcpublishing.com/photo/api/v2/photos/{}/"
EXPIRATION = "2000-01-01T00:00:00Z"


class DeleteDefunctPhotos:
    def __init__(
        self, 
        org: str, 
        arc_auth_header: Dict[str, str], 
        image_arc_id: str = "",
        images_csv: str = "",
        hard_delete: bool = False,
        dry_run: bool = False,
        max_workers: int = 8,
        batch_size: int = 100,
        rate_limit: int = 10
    ):
        self.arc_auth_header = arc_auth_header
        self.org = org
        self.org_for_filename = org.replace('sandbox.','')
        self.image_arc_id = image_arc_id
        self.images_csv = images_csv
        self.hard_delete = bool(hard_delete)
        self.dry_run = bool(dry_run)
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.rate_limiter = RateLimiter(rate_limit)
        self.logger = setup_logging(f"{self.org_for_filename}_delete_photos")
        
        # Statistics for benchmarking
        self.stats = {
            "total_photos_processed": 0,
            "photos_deleted": 0,
            "photos_expired": 0,
            "photos_failed": 0,
            'photos_skipped': 0,
            "api_calls": 0,
            "start_time": time.time()
        }

    def delete_single_photo(self, photo_id: str) -> Optional[Dict[str, Any]]:
        """Delete a single photo by its ARC ID"""
        if self.dry_run:
            self.stats["photos_deleted"] += 1
            self.logger.info(f"[DRY RUN] Would delete photo {photo_id}")
            return {"photo_id": photo_id, "status": "deleted", "response": 200}
        
        try:
            self.rate_limiter.wait_if_needed()
            res = requests.delete(
                PHOTO_API_URL.format(self.org, photo_id), 
                headers=self.arc_auth_header, 
                timeout=30
            )
            self.stats["api_calls"] += 1
            
            if res.ok:
                self.stats["photos_deleted"] += 1
                self.logger.info(f"Successfully deleted photo {photo_id}")
                return {"photo_id": photo_id, "status": "deleted", "response": res.status_code}
            else:
                self.stats["photos_failed"] += 1
                self.logger.error(f"Failed to delete photo {photo_id}: {res.status_code} - {res.text}")
                return {"photo_id": photo_id, "status": "failed", "response": res.status_code}
        except Exception as e:
            self.stats["photos_failed"] += 1
            self.logger.error(f"Exception deleting photo {photo_id}: {str(e)}")
            return {"photo_id": photo_id, "status": "error", "error": str(e)}

    def expire_single_photo(self, photo_id: str) -> Optional[Dict[str, Any]]:
        """Expire a single photo by setting its expiration date"""
        if self.dry_run:
            self.stats["photos_expired"] += 1
            self.logger.info(f"[DRY RUN] Would expire photo {photo_id}")
            return {"photo_id": photo_id, "status": "expired", "response": 200}
        
        try:
            # First get the photo
            self.rate_limiter.wait_if_needed()
            res_get = requests.get(
                PHOTO_API_URL.format(self.org, photo_id), 
                headers=self.arc_auth_header, 
                timeout=30
            )
            self.stats["api_calls"] += 1
            
            if res_get.ok:
                photo_ans = res_get.json()
                props = photo_ans.get("additional_properties", {})
                props["expiration_date"] = EXPIRATION
                props["published"] = False
                
                # Update the photo
                self.rate_limiter.wait_if_needed()
                res_put = requests.put(
                    PHOTO_API_URL.format(self.org, photo_id), 
                    headers=self.arc_auth_header, 
                    json=photo_ans, 
                    timeout=30
                )
                self.stats["api_calls"] += 1
                
                if res_put.ok:
                    self.stats["photos_expired"] += 1
                    self.logger.info(f"Successfully expired photo {photo_id}")
                    return {"photo_id": photo_id, "status": "expired", "response": res_put.status_code}
                else:
                    self.stats["photos_failed"] += 1
                    self.logger.error(f"Failed to expire photo {photo_id}: {res_put.status_code} - {res_put.text}")
                    return {"photo_id": photo_id, "status": "failed", "response": res_put.status_code}
            else:
                self.stats["photos_failed"] += 1
                self.logger.error(f"Failed to get photo {photo_id}: {res_get.status_code} - {res_get.text}")
                return {"photo_id": photo_id, "status": "failed", "response": res_get.status_code}
        except Exception as e:
            self.stats["photos_failed"] += 1
            self.logger.error(f"Exception expiring photo {photo_id}: {str(e)}")
            return {"photo_id": photo_id, "status": "error", "error": str(e)}

    def process_photo(self, photo_id: str) -> Optional[Dict[str, Any]]:
        """Process a single photo (delete or expire based on configuration)"""
        if self.hard_delete:
            return self.delete_single_photo(photo_id)
        else:
            return self.expire_single_photo(photo_id)

    def get_preserved_photo_ids(self, csv_file_path: str) -> set:
        """Get preserved photo IDs from the corresponding preserved CSV file"""
        preserved_ids = set()
        
        # Extract the suffix from the CSV filename
        # Example: photo_ids_to_delete_1577854800000-1578373200000.csv -> 1577854800000-1578373200000.csv
        base_name = os.path.basename(csv_file_path)
        if "photo_ids_to_delete_" in base_name:
            suffix = base_name.replace("photo_ids_to_delete_", "")
            preserved_csv_path = csv_file_path.replace("photo_ids_to_delete_", "preserved_photo_ids_")
            
            if os.path.isfile(preserved_csv_path):
                try:
                    with open(preserved_csv_path, newline="") as csvfile:
                        reader = csv.DictReader(csvfile)
                        for row in reader:
                            preserved_ids.add(row["ans_id"])
                    self.logger.info(f"Loaded {len(preserved_ids)} preserved photo IDs from {preserved_csv_path}")
                except Exception as e:
                    self.logger.warning(f"Could not read preserved photo IDs from {preserved_csv_path}: {str(e)}")
            else:
                self.logger.info(f"Preserved photo IDs file not found: {preserved_csv_path}")
        else:
            self.logger.warning(f"Could not determine preserved CSV path from filename: {base_name}")
        
        return preserved_ids

    @benchmark
    def delete_arcids(self) -> None:
        """HARD DELETES a single image or a list of images in a CSV file"""
        if self.images_csv:
            if os.path.isfile(self.images_csv):
                # Load photo IDs from CSV
                photo_ids = []
                with open(os.path.abspath(self.images_csv), newline="") as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                        photo_ids.append(row[0])
                
                # Get preserved photo IDs to skip
                preserved_ids = self.get_preserved_photo_ids(self.images_csv)
                
                # Filter out preserved photo IDs
                filtered_photo_ids = [pid for pid in photo_ids if pid not in preserved_ids]
                skipped_count = len(photo_ids) - len(filtered_photo_ids)
                self.stats["photos_skipped"] = skipped_count

                
                if skipped_count > 0:
                    self.logger.info(f"Skipped {skipped_count} photos that are in the preserved list")
                
                self.stats["total_photos_processed"] = len(filtered_photo_ids)
                self.logger.info(f"Loaded {len(filtered_photo_ids)} photos from CSV for deletion (after filtering preserved IDs)")
                
                # Process photos in parallel
                processor = ImagesParallelProcessor(
                    self.arc_auth_header,
                    self.org,
                    max_workers=self.max_workers,
                    rate_limit=self.rate_limiter.max_requests_per_second
                )
                results = processor.process_photos_parallel(
                    self.process_photo,
                    filtered_photo_ids,
                    chunk_size=self.batch_size
                )
                
                # Log results
                successful = len([r for r in results if r and r["status"] in ["deleted", "expired"]])
                failed = len([r for r in results if r and r["status"] in ["failed", "error"]])
                self.logger.info(f"Processing complete: {successful} successful, {failed} failed")
                
            else:
                self.logger.error(f"Path {self.images_csv} is not to a valid file")
        elif self.image_arc_id:
            # Process a single photo
            self.stats["total_photos_processed"] = 1
            result = self.process_photo(self.image_arc_id)
            if result:
                self.logger.info(f"Single photo processing complete: {result['status']}")
        else:
            self.logger.error("No image ARC ID or CSV file provided")

    def print_statistics(self) -> None:
        """Print processing statistics"""
        duration = time.time() - self.stats["start_time"]
        
        print("\n" + "="*50)
        if self.dry_run:
            print(f"DRY RUN STATISTICS {self.org.upper()}")
        else:
            print(f"PROCESSING STATISTICS {self.org.upper()}")
        print("="*50)
        print(f"Total photos processed: {self.stats['total_photos_processed']} (after filtering preserved IDs)")
        print(f"Photos deleted: {self.stats['photos_deleted']}")
        print(f"Photos expired: {self.stats['photos_expired']}")
        print(f"Photos skipped: {self.stats['photos_skipped']}")
        print(f"Photos failed: {self.stats['photos_failed']}")
        if not self.dry_run:
            print(f"API calls made: {self.stats['api_calls']}")
        print(f"Total duration: {format_duration(duration)}")
        if self.dry_run:
            print("*** DRY RUN - NO ACTUAL CHANGES MADE ***")
        print("="*50)

    @benchmark
    def run(self) -> None:
        """Main execution method"""
        if self.dry_run:
            self.logger.info("Starting photo deletion/expiration process (DRY RUN)")
        else:
            self.logger.info("Starting photo deletion/expiration process")
        self.delete_arcids()
        self.print_statistics()


def main():
    """Main function to run the photo deletion/expiration script"""
    parser = argparse.ArgumentParser(description="Delete or expire photos from Arc XP Photo Center")
    parser.add_argument("--org", required=True, help="Organization (e.g., washpost)")
    parser.add_argument("--bearer-token", required=True, dest="bearer_token", help="Bearer token for API authentication")
    parser.add_argument("--environment", choices=["sandbox", "production"], default="sandbox", help="Environment to run in (default: sandbox)")
    parser.add_argument("--image-arc-id", help="Single image ARC ID to process")
    parser.add_argument("--images-csv", help="CSV file containing image ARC IDs to process")
    parser.add_argument("--hard-delete", action="store_true", help="Hard delete instead of expire")
    parser.add_argument("--dry-run", action="store_true", help="Simulate operations without making actual changes")
    parser.add_argument("--max-workers", type=int, default=8, help="Maximum number of worker threads")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--rate-limit", type=int, default=10, help="API rate limit (requests per second)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.image_arc_id and not args.images_csv:
        print("Error: Must provide either --image-arc-id or --images-csv")
        return 1
    
    # Setup authentication header
    arc_auth_header = {"Authorization": f"Bearer {args.bearer_token}"}
    
    # Modify org based on environment
    org_with_env = args.org
    if args.environment == "sandbox":
        org_with_env = f"sandbox.{args.org}"
    
    # Create and run the processor
    processor = DeleteDefunctPhotos(
        org=org_with_env,
        arc_auth_header=arc_auth_header,
        image_arc_id=args.image_arc_id,
        images_csv=args.images_csv,
        hard_delete=args.hard_delete,
        dry_run=args.dry_run,
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        rate_limit=args.rate_limit
    )
    
    processor.run()
    return 0


if __name__ == "__main__":
    exit(main()) 