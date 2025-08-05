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
from .delete_redirects_parallel_processor import RedirectsDeleteParallelProcessor

DRAFT_API_URL = "https://api.{}.arcpublishing.com/draft/v1/redirect/{}/{}"


class DeleteRedirects:
    def __init__(
            self,
            org: str,
            arc_auth_header: Dict[str, str],
            redirect_url: str = "",
            redirect_website: str = "",
            redirects_csv: str = "",
            dry_run: bool = False,
            max_workers: int = 8,
            batch_size: int = 100,
            rate_limit: int = 10
    ):
        self.arc_auth_header = arc_auth_header
        self.org = org
        self.org_for_filename = org.replace("sandbox.", "")
        self.redirect_url = redirect_url
        self.redirect_website = redirect_website
        self.redirects_csv = redirects_csv
        self.dry_run = bool(dry_run)
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.rate_limiter = RateLimiter(rate_limit)
        self.logger = setup_logging(f"{self.org_for_filename}_redirects")

        # Statistics for benchmarking
        self.stats = {
            "total_redirects_processed": 0,
            "redirects_deleted": 0,
            "redirects_failed": 0,
            "api_calls": 0,
            "start_time": time.time()
        }

    def delete_single_redirect(self, redirect_url: str, redirect_website: str) -> Optional[Dict[str, Any]]:
        """Delete a single redirect by its canonical URL"""
        if self.dry_run:
            self.stats["redirects_deleted"] += 1
            self.logger.info(f"[DRY RUN] Would delete {redirect_website} redirect {redirect_url}")
            return {"redirect_url": redirect_url, "website": redirect_website, "status": "deleted", "response": 200}

        try:
            self.rate_limiter.wait_if_needed()
            res = requests.delete(
                DRAFT_API_URL.format(self.org, redirect_website, redirect_url),
                headers=self.arc_auth_header,
                timeout=30
            )
            self.stats["api_calls"] += 1

            if res.ok:
                self.stats["redirects_deleted"] += 1
                self.logger.info(f"Successfully deleted {redirect_website} redirect {redirect_url}")
                return {"redirect_url": redirect_url, "website": redirect_website, "status": "deleted", "response": res.status_code}
            else:
                self.stats["redirects_failed"] += 1
                self.logger.error(f"Failed to delete {redirect_website} redirect {redirect_url}: {res.status_code} - {res.text}")
                return {"redirect_url": redirect_url, "website": redirect_website, "status": "failed", "response": res.status_code}
        except Exception as e:
            self.stats["redirects_failed"] += 1
            self.logger.error(f"Exception deleting {redirect_website} redirect {redirect_url}: {str(e)}")
            return {"redirect_url": redirect_url, "redirect_website": redirect_website, "status": "error", "error": str(e)}

    def delete_redirects_parallel(self, redirect_items: List[tuple]) -> List[Dict[str, Any]]:
        """Delete multiple redirects in parallel using the parallel processor"""
        # Initialize parallel processor
        parallel_processor = RedirectsDeleteParallelProcessor(
            arc_auth_header=self.arc_auth_header,
            org=self.org,
            max_workers=self.max_workers,
            rate_limit=self.rate_limiter.max_requests_per_second,
            dry_run=self.dry_run
        )
        
        # Process redirects in parallel
        results = parallel_processor.process_redirects_parallel(
            delete_func=self.delete_single_redirect,
            redirect_items=redirect_items,
            chunk_size=self.batch_size,
            description="Deleting redirects"
        )
        
        # Update statistics from parallel processor
        parallel_stats = parallel_processor.get_statistics()
        self.stats.update(parallel_stats)
        
        return results

    @benchmark
    def delete_redirects(self) -> None:
        """HARD DELETES a single redirect or a list of redirects in a CSV file
            csv file contents contains two columns in the format:
            redirect_url,website
        """
        if self.redirects_csv:
            if os.path.isfile(self.redirects_csv):
                # Load redirect urls from CSV
                redirect_urls = []
                with open(os.path.abspath(self.redirects_csv), newline="") as csvfile:
                    reader = csv.reader(csvfile)
                    #TODO: validate the row data is probably correct.  First column is a relative URL.  Second column is text with appropriate slugifyable characters
                    for row in reader:
                        redirect_urls.append((row[0], row[1]))

                    self.stats["total_redirects_processed"] = len(redirect_urls)
                    self.logger.info(
                        f"Loaded {len(redirect_urls)} redirects from CSV for deletion")

                    # Delete redirects in parallel using the parallel processor
                    results = self.delete_redirects_parallel(redirect_urls)
                    
                    # Print final statistics
                    successful_deletions = sum(1 for r in results if r.get("status") == "deleted")
                    failed_deletions = len(results) - successful_deletions
                    processing_time = time.time() - self.stats["start_time"]
                    
                    print(f"\n📊 Deletion Statistics:")
                    print(f"  • Total processed: {self.stats['total_redirects_processed']}")
                    print(f"  • Successfully deleted: {successful_deletions}")
                    print(f"  • Failed deletions: {failed_deletions}")
                    print(f"  • Total API calls: {self.stats['api_calls']}")
                    print(f"  • Processing time: {processing_time:.2f} seconds")
                    print(f"  • Success rate: {(successful_deletions / len(results) * 100):.1f}%" if results else "  • Success rate: 0.0%")

            else:
                self.logger.error(f"Path {self.redirects_csv} is not to a valid file")
        elif self.redirect_url and self.redirect_website:
            # Process a single redirect
            self.stats["total_redirects_processed"] = 1
            result = self.delete_single_redirect(self.redirect_url, self.redirect_website)
            if result:
                processing_time = time.time() - self.stats["start_time"]
                
                print(f"\n📊 Single Redirect Deletion Statistics:")
                print(f"  • Status: {result['status']}")
                print(f"  • Processing time: {processing_time:.2f} seconds")
                print(f"  • API calls: {self.stats['api_calls']}")
                if result.get('response'):
                    print(f"  • Response code: {result['response']}")
                if result.get('error'):
                    print(f"  • Error: {result['error']}")
        else:
            self.logger.error("No redirect URL or CSV file provided")


def main():
    """Main function to run the redirects deletion script"""
    parser = argparse.ArgumentParser(description="Delete document or vanity redirect URLs from Arc XP Draft API")
    parser.add_argument("--org", required=True, help="Organization (e.g., washpost)")
    parser.add_argument("--bearer-token", required=True, dest="bearer_token",
                        help="Bearer token for API authentication")
    parser.add_argument("--environment", choices=["sandbox", "production"], default="sandbox",
                        help="Environment to run in (default: sandbox)")
    parser.add_argument("--redirect-url", help="Single redirect URL to delete")
    parser.add_argument("--redirect-website", help="Single redirect website location")
    parser.add_argument("--redirects-csv", help="CSV file containing redirect URLs to delete")
    parser.add_argument("--dry-run", action="store_true", help="Simulate operations without making actual changes")
    parser.add_argument("--max-workers", type=int, default=8, help="Maximum number of worker threads")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--rate-limit", type=int, default=4, help="API rate limit (requests per second)")

    args = parser.parse_args()

    # Validate arguments
    if not (args.redirect_url and args.redirect_website) and not args.redirects_csv:
        print("Error: Must provide either --redirect-url and --redirect-website or --redirects-csv")
        return 1

    # Setup authentication header
    arc_auth_header = {"Authorization": f"Bearer {args.bearer_token}"}

    # Modify org based on environment
    org_with_env = args.org
    if args.environment == "sandbox":
        org_with_env = f"sandbox.{args.org}"

    # Create and run the processor
    doit = DeleteRedirects(
        org=org_with_env,
        arc_auth_header=arc_auth_header,
        redirect_url=args.redirect_url,
        redirect_website=args.redirect_website,
        redirects_csv=args.redirects_csv,
        dry_run=args.dry_run,
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        rate_limit=args.rate_limit
    )

    doit.delete_redirects()
    return 0


if __name__ == "__main__":
    exit(main())