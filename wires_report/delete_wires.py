import argparse
import csv
import os
import time
from typing import List, Dict, Any, Optional

import requests

from utils import (
    setup_logging,
    benchmark,
    RateLimiter,
)
from .delete_wires_parallel_processor import StoriesDeleteParallelProcessor

DRAFT_DELETE_URL = "https://api.{}.arcpublishing.com/draft/v1/story/{}"
DRAFT_UNPUBLISH_URL = "https://api.{}.arcpublishing.com/draft/v1/story/{}/revision/published"


class DeleteStories:
    def __init__(
            self,
            org: str,
            arc_auth_header: Dict[str, str],
            arc_id: str = "",
            wires_csv: str = "",
            dry_run: bool = False,
            max_workers: int = 8,
            batch_size: int = 100,
            rate_limit: int = 10
    ):
        self.arc_auth_header = arc_auth_header
        self.org = org
        self.org_for_filename = org.replace("sandbox.", "")
        self.arc_id = arc_id
        self.wires_csv = wires_csv
        self.dry_run = bool(dry_run)
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.rate_limiter = RateLimiter(rate_limit)
        self.logger = setup_logging(f"{self.org_for_filename}_wires")

        # Statistics for benchmarking
        self.stats = {
            "total_wires_processed": 0,
            "wires_deleted": 0,
            "wires_failed": 0,
            "api_calls": 0,
            "start_time": time.time()
        }

    def delete_single_story(self, arc_id: str,) -> Optional[Dict[str, Any]]:
        """Delete a single story by its arc id"""
        if self.dry_run:
            self.stats["wires_deleted"] += 1
            self.logger.info(f"[DRY RUN] Would delete {arc_id}")
            return {"arc_id": arc_id, "status": "deleted", "response": 200}

        try:
            self.rate_limiter.wait_if_needed()
            # First unpublish the story
            res = requests.delete(
                DRAFT_UNPUBLISH_URL.format(self.org, arc_id),
                headers=self.arc_auth_header,
                timeout=30
            )
            self.stats["api_calls"] += 1
            
            # Wait for unpublish to complete
            time.sleep(5)
            
            # Then delete the story
            res = requests.delete(
                DRAFT_DELETE_URL.format(self.org, arc_id),
                headers=self.arc_auth_header,
                timeout=30
            )
            self.stats["api_calls"] += 2

            if res.ok:
                self.stats["stories_deleted"] += 1
                self.logger.info(f"Successfully deleted {arc_id}")
                return {"arc_id": arc_id, "status": "deleted", "response": res.status_code}
            else:
                self.stats["stories_failed"] += 1
                self.logger.error(f"Failed to delete {arc_id}: {res.status_code} - {res.text}")
                return {"arc_id": arc_id, "status": "failed", "response": res.status_code}
        except Exception as e:
            self.stats["stories_failed"] += 1
            self.logger.error(f"Exception deleting {arc_id}: {str(e)}")
            return {"arc_id": arc_id, "status": "error", "error": str(e)}

    def delete_stories_parallel(self, story_items: List[str]) -> List[Dict[str, Any]]:
        """Delete multiple stories in parallel using the parallel processor"""
        # Initialize parallel processor
        parallel_processor = StoriesDeleteParallelProcessor(
            arc_auth_header=self.arc_auth_header,
            org=self.org,
            max_workers=self.max_workers,
            rate_limit=self.rate_limiter.max_requests_per_second,
            dry_run=self.dry_run
        )
        
        # Process stories in parallel
        results = parallel_processor.process_stories_parallel(
            delete_func=self.delete_single_story,
            story_items=story_items,
            chunk_size=self.batch_size,
            description="Deleting stories"
        )
        
        # Update statistics from parallel processor
        parallel_stats = parallel_processor.get_statistics()
        self.stats.update(parallel_stats)
        
        return results

    @benchmark
    def delete_stories(self) -> None:
        """HARD DELETES a single story or a list of stories in a CSV file
            csv file contains a single column of arc_ids
        """
        if self.wires_csv:
            if os.path.isfile(self.wires_csv):
                # Load arc ids from CSV
                arc_ids = []
                with open(os.path.abspath(self.wires_csv), newline="") as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                        arc_ids.append(row[0])

                    self.stats["total_stories_processed"] = len(arc_ids)
                    self.logger.info(
                        f"Loaded {len(arc_ids)} stories from CSV for deletion")

                    # Delete stories in parallel using the parallel processor
                    results = self.delete_stories_parallel(arc_ids)
                    
                    # Print final statistics
                    successful_deletions = sum(1 for r in results if r.get("status") == "deleted")
                    failed_deletions = len(results) - successful_deletions
                    processing_time = time.time() - self.stats["start_time"]
                    
                    print(f"\n📊 Deletion Statistics:")
                    print(f"  • Total processed: {self.stats['total_stories_processed']}")
                    print(f"  • Successfully deleted: {successful_deletions}")
                    print(f"  • Failed deletions: {failed_deletions}")
                    print(f"  • Total API calls: {self.stats['api_calls']}")
                    print(f"  • Processing time: {processing_time:.2f} seconds")
                    print(f"  • Success rate: {(successful_deletions / len(results) * 100):.1f}%" if results else "  • Success rate: 0.0%")

            else:
                self.logger.error(f"Path {self.wires_csv} is not to a valid file")
        elif self.arc_id:
            # Process a single story
            self.stats["total_stories_processed"] = 1
            result = self.delete_single_story(self.arc_id)
            if result:
                processing_time = time.time() - self.stats["start_time"]
                
                print(f"\n📊 Single Story Deletion Statistics:")
                print(f"  • Status: {result['status']}")
                print(f"  • Processing time: {processing_time:.2f} seconds")
                print(f"  • API calls: {self.stats['api_calls']}")
                if result.get('response'):
                    print(f"  • Response code: {result['response']}")
                if result.get('error'):
                    print(f"  • Error: {result['error']}")
        else:
            self.logger.error("No arc id or CSV file provided")


def main():
    """Main function to run the wires deletion script"""
    parser = argparse.ArgumentParser(description="Delete wires stories from Arc XP Draft API")
    parser.add_argument("--org", required=True, help="Organization (e.g., washpost)")
    parser.add_argument("--bearer-token", required=True, dest="bearer_token",
                        help="Bearer token for API authentication")
    parser.add_argument("--environment", choices=["sandbox", "production"], default="sandbox",
                        help="Environment to run in (default: sandbox)")
    parser.add_argument("--arc-id", help="Single arc id to delete")
    parser.add_argument("--wires-csv", help="CSV file containing arc ids to delete")
    parser.add_argument("--dry-run", action="store_true", help="Simulate operations without making actual changes")
    parser.add_argument("--max-workers", type=int, default=8, help="Maximum number of worker threads")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--rate-limit", type=int, default=4, help="DRAFT API rate limit (requests per second)")

    args = parser.parse_args()

    # Validate arguments
    if not args.arc_id and not args.wires_csv:
        print("Error: Must provide either --arc-id or --wires-csv")
        return 1

    # Setup authentication header
    arc_auth_header = {"Authorization": f"Bearer {args.bearer_token}"}

    # Modify org based on environment
    org_with_env = args.org
    if args.environment == "sandbox":
        org_with_env = f"sandbox.{args.org}"

    # Create and run the processor
    doit = DeleteStories(
        org=org_with_env,
        arc_auth_header=arc_auth_header,
        arc_id=args.arc_id,
        wires_csv=args.wires_csv,
        dry_run=args.dry_run,
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        rate_limit=args.rate_limit
    )

    doit.delete_stories()
    return 0


if __name__ == "__main__":
    exit(main())