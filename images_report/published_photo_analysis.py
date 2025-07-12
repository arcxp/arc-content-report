import argparse
import csv
import datetime
import os
import pprint
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import sqlite3
from jmespath import Options, search
from decouple import config

from utils import (
    setup_logging, 
    benchmark, 
    RateLimiter, 
    get_csv_path,
    get_db_path,
    format_timestamp,
    format_duration,
    PerformanceBenchmark
)
from .parallel_processor import ImagesParallelProcessor

PHOTO_API_SEARCH_URL_WITH_DATES = "https://api.{}.arcpublishing.com/photo/api/v2/photos?published=true&startDateUploaded={}&endDateUploaded={}"
PHOTO_API_SEARCH_URL_ALL_PHOTOS = "https://api.{}.arcpublishing.com/photo/api/v2/photos?published=true"
PHOTO_API_SEARCH_URL_PUBLISHED_WIRES = "https://api.{}.arcpublishing.com/photo/api/v2/photos?published=true&sourceType=wires"
PHOTO_API_SINGLE_ITEM_URL = "https://api.{}.arcpublishing.com/photo/api/v2/photos/{}/"
CAPI_STORY_SEARCH_URL = "https://api.{}.arcpublishing.com/content/v4/search?website={}&published=true&_sourceInclude=type,promo_items.lead_art.url,promo_items.basic.url,content_elements.url,related_content&q={}"
CAPI_REFERENCES_URL = "https://api.{}.arcpublishing.com/content/v4/referenced-content/image/{}/references"


@dataclass
class ReportItem:
    ans_id: str
    ans_location: Optional[str] = None
    source_id: Optional[str] = None
    website: Optional[str] = None


class IncompleteLightboxCacheDbException(Exception):
    def __init__(
        self,
        message="databases/lightbox_photo_cache.db must exist and be initialized with data for the correct environment. run the script create_lightbox_cache.py to completion.",
    ):
        self.message = message
        super().__init__(self.message)


class CombinedPhotoAnalysis:
    def __init__(
        self,
        org: str,
        arc_auth_header: Dict[str, str],
        image_arc_id: str = "",
        start_date: int = 0,
        end_date: int = 0,
        offset: int = 0,
        source: str = "",
        website_list: List[str] = None,
        max_workers: int = 8,
        batch_size: int = 100,
        rate_limit: int = 10,
        pc_published_wires: bool = False
    ):
        self.arc_auth_header = arc_auth_header
        self.org = org
        self.org_for_filename = org.replace('sandbox.','')
        self.start_date = start_date
        self.end_date = end_date
        self.offset_scriptarg = offset
        self.image_arc_id = image_arc_id
        self.source = source
        self.website_list = website_list or []
        self.pc_published_wires = pc_published_wires
        self.images_list = []
        self.images_preserved = []
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.rate_limiter = RateLimiter(rate_limit)
        self.logger = setup_logging(f"{self.org_for_filename}_photo_analysis")
        
        # Statistics for benchmarking
        self.stats = {
            "total_photos_processed": 0,
            "photos_to_delete": 0,
            "photos_preserved": 0,
            "photos_in_lightbox": 0,
            "photos_in_stories": 0,
            "photos_in_galleries": 0,
            "api_calls": 0,
            "start_time": time.time()
        }
        
        # Database path setup for lightbox checks (connections created per thread)
        if "sandbox." in self.org:
            db_name = config("LIGHTBOX_CACHE_DB_SANDBOX")
        else:
            db_name = config("LIGHTBOX_CACHE_DB")
        db_name = f"{self.org_for_filename}_{db_name}"

        self.db_path = get_db_path(db_name)
        self.logger.info(f"Lightbox database path: {self.db_path}")

    @benchmark
    def query_single_photo(self, arcid: str) -> None:
        """Query a single photo by its ARC ID"""
        self.logger.info(f"Checking single photo {arcid}")
        
        res = requests.get(
            PHOTO_API_SINGLE_ITEM_URL.format(self.org, arcid),
            headers=self.arc_auth_header,
            timeout=30
        )
        self.stats["api_calls"] += 1
        
        if res.ok:
            results = res.json()
            self.images_list = [arcid]
            self.stats["total_photos_processed"] = 1
            self.logger.info(f"Successfully retrieved photo {arcid}")
        else:
            self.logger.error(f"Failed to retrieve photo {arcid}: {res.status_code}")

    def get_photo_url(self):
        """
        Determine if is used and select the appropriate URL template based on filtering options.
        Can query with or without source filter, with or without date range, with or without published wires filter
        Returns (url, use_date_filter)
        """
        use_date_filter = self.start_date > 0 and self.end_date > 0
        if self.pc_published_wires:
            # --pc-published-wires flag is set
            if use_date_filter:
                url_template = f"{PHOTO_API_SEARCH_URL_PUBLISHED_WIRES}&startDateUploaded={{}}&endDateUploaded={{}}"
                self.logger.info(f"Starting published wires date range query from {format_timestamp(self.start_date)} to {format_timestamp(self.end_date)}")
            else:
                url_template = PHOTO_API_SEARCH_URL_PUBLISHED_WIRES
                self.logger.info(f"Starting published wires query (all dates)")
        elif use_date_filter:
            # Date filtering without --pc-published-wires
            if self.source:
                url_template = f"{PHOTO_API_SEARCH_URL_WITH_DATES}&source={self.source}"
                self.logger.info(f"Starting photo center query, published, source id '{self.source}' date range query from {format_timestamp(self.start_date)} to {format_timestamp(self.end_date)}")
            else:
                url_template = PHOTO_API_SEARCH_URL_WITH_DATES
                self.logger.info(f"Starting photo center query, published, (all sources) date range from {format_timestamp(self.start_date)} to {format_timestamp(self.end_date)}")
        else:
            # No date filtering, no --pc-published-wires
            if self.source:
                url_template = f"{PHOTO_API_SEARCH_URL_ALL_PHOTOS}&source={self.source}"
                self.logger.info(f"Starting photo center query, published, source id '{self.source}' (all dates)")
            else:
                url_template = PHOTO_API_SEARCH_URL_ALL_PHOTOS
                self.logger.info(f"Starting photo center query (published, all sources, all dates)")

        # Construct URL based on filtering options
        if self.pc_published_wires:
            if use_date_filter:
                url = url_template.format(self.org, self.start_date, self.end_date)
            else:
                url = url_template.format(self.org)
        elif use_date_filter:
            if self.source:
                url = url_template.format(self.org, self.start_date, self.end_date)
            else:
                url = url_template.format(self.org, self.start_date, self.end_date)
        else:
            url = url_template.format(self.org)
        return url, use_date_filter

    @benchmark
    def query_photos(self, offset_localarg: int = None) -> None:
        """
        Query photos with pagination support
        Can query with or without source filter, with or without date range, with or without published wires filter
        """
        offset = offset_localarg if offset_localarg is not None else self.offset_scriptarg or 0
        all_photos = []
        current_offset = int(offset)
        page_count = 0

        # Construct photo center url with appropriate filters
        url, use_date_filter = self.get_photo_url()

        while True:
            params = {"limit": 100, "offset": current_offset}
            
            self.rate_limiter.wait_if_needed()

            res = requests.get(
                url,
                headers=self.arc_auth_header,
                params=params,
                timeout=30
            )
            self.stats["api_calls"] += 1
            
            if not res.ok:
                self.logger.error(f"API request failed: {res.status_code} - {res.text}")
                break
                
            result = res.json()
            photo_ids = search("[*]._id", result)
            
            if not photo_ids:
                self.logger.info("No more photos found, ending pagination")
                break
                
            all_photos.extend(photo_ids)
            page_count += 1
            
            self.logger.info(f"Page {page_count}: Retrieved {len(photo_ids)} photos (total so far: {len(all_photos)}) of {int(res.headers.get('x-results-total', 0))}")
            
            # Check if we've reached the end
            total_results = int(res.headers.get('x-results-total', 0))
            if current_offset + len(photo_ids) >= total_results:
                self.logger.info(f"Reached end of results. Total photos: {len(all_photos)}")
                break
                
            current_offset += 100
            
            # Safety check to prevent infinite loops
            if page_count > 1000:  # Arbitrary limit
                self.logger.warning("Reached maximum page limit, stopping pagination")
                break
        
        self.images_list = all_photos
        self.stats["total_photos_processed"] = len(all_photos)
        
        # Log completion message based on filtering options
        if self.pc_published_wires:
            if use_date_filter:
                self.logger.info(f"Completed published wires date range query. Total photos to process: {len(all_photos)}")
            else:
                self.logger.info(f"Completed published wires query (all dates). Total photos to process: {len(all_photos)}")
        elif use_date_filter:
            if self.source:
                self.logger.info(f"Completed published source id '{self.source}' date range query. Total photos to process: {len(all_photos)}")
            else:
                self.logger.info(f"Completed published date range query (all sources). Total photos to process: {len(all_photos)}")
        else:
            if self.source:
                self.logger.info(f"Completed published source id '{self.source}' query (all dates). Total photos to process: {len(all_photos)}")
            else:
                self.logger.info(f"Completed query (published, all sources, all dates). Total photos to process: {len(all_photos)}")

    def check_photo_references(self, photo_id: str) -> Optional[Dict[str, Any]]:
        """Check if a photo is referenced in published content"""
        try:
            self.rate_limiter.wait_if_needed()
            res = requests.get(
                CAPI_REFERENCES_URL.format(self.org, photo_id), 
                headers=self.arc_auth_header,
                timeout=30
            )
            self.stats["api_calls"] += 1
            
            if res.ok:
                result = res.json()
                if True in search("references[*].published", result):
                    return {
                        "photo_id": photo_id,
                        "location": f"referenced-content {str(set(search('references[*].reference_type', result)))}",
                        "website": str(set(search("references[*].website_id", result)))
                    }
            return None
        except Exception as e:
            self.logger.error(f"Error checking references for photo {photo_id}: {str(e)}")
            return None

    def check_photo_fulltext(self, photo_id: str) -> Optional[Dict[str, Any]]:
        """Check if a photo is used in published galleries or stories via fulltext search"""
        try:
            for website in self.website_list:
                self.rate_limiter.wait_if_needed()
                res = requests.get(
                    CAPI_STORY_SEARCH_URL.format(self.org, website, photo_id), 
                    headers=self.arc_auth_header,
                    timeout=30
                )
                self.stats["api_calls"] += 1
                
                if res.ok:
                    result = res.json()
                    if result["count"] > 0:
                        # Check if it's in a gallery
                        if "gallery" in search("content_elements[*].type", result):
                            return {
                                "photo_id": photo_id,
                                "location": "gallery",
                                "website": website
                            }
            return None
        except Exception as e:
            self.logger.error(f"Error checking fulltext for photo {photo_id}: {str(e)}")
            return None

    def check_lightbox_photo(self, photo_id: str) -> Optional[Dict[str, Any]]:
        """Check if a photo exists in any lightbox"""
        try:
            # Create a new connection for this thread
            with sqlite3.connect(self.db_path) as conn:
                sql = "SELECT photo_id FROM lightbox_photo_cache WHERE photo_id = ?;"
                cursor = conn.cursor()
                cursor.execute(sql, (photo_id,))
                rows = cursor.fetchall()
                
                if bool(rows):
                    return {
                        "photo_id": photo_id,
                        "location": "lightbox",
                        "website": ""
                    }
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Database error checking lightbox for photo {photo_id}: {e}")
            return None

    @benchmark
    def process_photos_analysis(self) -> None:
        """Process all photos analysis - check references, fulltext, and lightboxes in parallel"""
        if not self.images_list:
            self.logger.warning("No photos to process")
            return
            
        self.logger.info(f"Starting analysis processing of {len(self.images_list)} photos")
        
        # Create parallel processor instance
        processor = ImagesParallelProcessor(
            self.arc_auth_header,
            self.org,
            max_workers=self.max_workers,
            rate_limit=self.rate_limiter.max_requests_per_second
        )
        
        # Step 1: Check references in parallel
        self.logger.info("Step 1: Checking photo references...")
        preserved_from_references = processor.process_photos_parallel(
            self.check_photo_references,
            self.images_list,
            chunk_size=self.batch_size
        )
        
        # Remove photos that are referenced
        for item in preserved_from_references:
            if item and item["photo_id"] in self.images_list:
                self.images_list.remove(item["photo_id"])
                self.images_preserved.append(ReportItem(
                    ans_id=item["photo_id"],
                    ans_location=item["location"],
                    source_id=self.source,
                    website=item["website"]
                ).__dict__)
                self.stats["photos_in_stories"] += 1
        
        self.logger.info(f"Reference check complete. {len([x for x in preserved_from_references if x])} photos preserved")
        
        # Step 2: Check fulltext usage in parallel (only for remaining photos)
        if self.images_list:
            self.logger.info("Step 2: Checking photo fulltext usage...")
            preserved_from_fulltext = processor.process_photos_parallel(
                self.check_photo_fulltext,
                self.images_list,
                chunk_size=self.batch_size
            )
            
            # Remove photos that are used in galleries
            for item in preserved_from_fulltext:
                if item and item["photo_id"] in self.images_list:
                    self.images_list.remove(item["photo_id"])
                    self.images_preserved.append(ReportItem(
                        ans_id=item["photo_id"],
                        ans_location=item["location"],
                        source_id=self.source,
                        website=item["website"]
                    ).__dict__)
                    self.stats["photos_in_galleries"] += 1
            
            self.logger.info(f"Fulltext check complete. {len([x for x in preserved_from_fulltext if x])} photos preserved")
        
        # Step 3: Check lightbox usage in parallel (only for remaining photos)
        if self.images_list:
            self.logger.info("Step 3: Checking lightbox usage...")
            preserved_from_lightbox = processor.process_photos_parallel(
                self.check_lightbox_photo,
                self.images_list,
                chunk_size=self.batch_size
            )
            
            # Remove photos that are in lightboxes
            for item in preserved_from_lightbox:
                if item and item["photo_id"] in self.images_list:
                    self.images_list.remove(item["photo_id"])
                    self.images_preserved.append(ReportItem(
                        ans_id=item["photo_id"],
                        ans_location=item["location"],
                        source_id=self.source,
                        website=item["website"]
                    ).__dict__)
                    self.stats["photos_in_lightbox"] += 1
            
            self.logger.info(f"Lightbox check complete. {len([x for x in preserved_from_lightbox if x])} photos preserved")
        
        self.stats["photos_to_delete"] = len(self.images_list)
        self.stats["photos_preserved"] = len(self.images_preserved)
        
        self.logger.info(f"Analysis processing complete. {len(self.images_list)} photos to delete, {len(self.images_preserved)} preserved")

    def write_csv_files(self, filenames: List[str] = None) -> None:
        """Write results to CSV files in the spreadsheets directory"""
        if filenames is None:
            filenames = [f"{self.org_for_filename}_preserved_photo_ids_", f"{self.org_for_filename}_photo_ids_to_delete_"]
            
        x = datetime.datetime.now()
        if self.image_arc_id:
            name_suffix = x.strftime("%Y-%m-%d.csv")
        elif self.start_date > 0 and self.end_date > 0:
            name_suffix = f"{self.start_date}-{self.end_date}.csv"
        else:
            name_suffix = "all_dates.csv"
        if "sandbox." in self.org:
            name_suffix = "sandbox_" + name_suffix

        # Write two files, a list of ids to delete and a list of ids to preserve
        for name in filenames:
            file_name = get_csv_path(name + name_suffix)
            self.logger.info(f"Writing {file_name}")
            
            with open(file_name, "a", newline="") as fw:
                if "preserved" in file_name:
                    if len(self.images_preserved):
                        # Check if file is empty (no header yet)
                        file_is_empty = os.path.getsize(file_name) == 0
                        
                        writer = csv.DictWriter(
                            fw, fieldnames=["ans_id", "ans_location", "source_id", "website"]
                        )
                        
                        # Only write header if file is empty
                        if file_is_empty:
                            writer.writeheader()
                            
                        for row in self.images_preserved:
                            writer.writerow(row)
                        self.logger.info(f"Wrote {len(self.images_preserved)} preserved photos to {file_name}")
                    else:
                        self.logger.info("No preserved images data to write")
                else:
                    if len(self.images_list):
                        writer = csv.writer(fw)
                        for x in self.images_list:
                            writer.writerow([x])
                        self.logger.info(f"Wrote {len(self.images_list)} image ANS ids to delete in {file_name}")
                    else:
                        self.logger.info("No images to delete data")

            # Remove empty files
            if os.path.getsize(file_name) == 0:
                os.remove(file_name)
                self.logger.info(f"Removed empty file {file_name}")

    def print_statistics(self) -> None:
        """Print comprehensive processing statistics"""
        duration = time.time() - self.stats["start_time"]
        
        self.logger.info("=" * 60)
        self.logger.info(f"PUBLISHED PHOTO ANALYSIS STATISTICS {self.org.upper()}")
        self.logger.info("=" * 60)
        # Check if date filtering was used
        if self.start_date > 0 and self.end_date > 0:
            self.logger.info(f"Date range processed: {format_timestamp(self.start_date)} to {format_timestamp(self.end_date)}")
        else:
            self.logger.info("Date range: None (all dates queried)")
            
        if self.pc_published_wires:
            self.logger.info("Photo Center filter: Only published wires")
        elif self.source:
            self.logger.info(f"Photo Center published source id processed: {self.source}")
        else:
            self.logger.info("Photo Center source id: None (all published sources queried)")
        self.logger.info(f"Total photos processed: {self.stats['total_photos_processed']}")
        self.logger.info(f"Photos to delete: {self.stats['photos_to_delete']}")
        self.logger.info(f"Photos preserved: {self.stats['photos_preserved']}")
        self.logger.info(f"  - In stories: {self.stats['photos_in_stories']}")
        self.logger.info(f"  - In galleries: {self.stats['photos_in_galleries']}")
        self.logger.info(f"  - In lightboxes: {self.stats['photos_in_lightbox']}")
        self.logger.info(f"Total API calls: {self.stats['api_calls']}")
        self.logger.info(f"Processing time: {format_duration(duration)}")
        if self.stats['total_photos_processed'] > 0:
            self.logger.info(f"Average time per photo: {duration/self.stats['total_photos_processed']:.3f}s")
        self.logger.info("=" * 60)

    @benchmark
    def doit(self) -> None:
        """Main execution method"""
        self.logger.info("Starting published photo analysis process")
        
        if self.image_arc_id:
            self.query_single_photo(self.image_arc_id)
        else:
            self.query_photos()
            
        if self.images_list:
            self.process_photos_analysis()
            self.write_csv_files()
        
        self.print_statistics()


def main():
    """Main function to run the published photo analysis script"""
    parser = argparse.ArgumentParser(description="Analyze published photos to identify candidates for deletion")
    parser.add_argument(
        "--org",
        dest="org",
        help="arc xp organization id; if sandbox environment this is sandbox.{org}",
        required=True
    )
    parser.add_argument(
        "--bearer-token",
        dest="bearer_token",
        help="organization bearer token; must match org and environment",
        required=True
    )
    parser.add_argument(
        "--environment",
        choices=["sandbox", "production"],
        default="sandbox",
        help="Environment to run in (default: sandbox)"
    )
    parser.add_argument("--image-arc-id", dest="image_arc_id", default="")
    parser.add_argument(
        "--start-date",
        dest="start_date",
        help="start date in this format: 2019-01-01",
        default="",
    )
    parser.add_argument(
        "--end-date",
        dest="end_date",
        help="end date in this format: 2019-01-31",
        default="",
    )
    parser.add_argument(
        "--offset", dest="offset", help="Photo Api query offset", default="0"
    )
    parser.add_argument(
        "--pc-source-id",
        dest="pc_source_id",
        help="the distributor id from the Photo Center source parameter in the PC UI address bar (optional - if not provided, queries all sources)",
        default="",
    )
    parser.add_argument(
        "--pc-published-wires",
        dest="pc_published_wires",
        action="store_true",
        help="query only published wires photos (cannot be used with --pc-source-id)",
    )
    parser.add_argument(
        "--websites-list",
        dest="website_list",
        help="websites to be checked for stories where the image may be used. item contains a comma delimited list",
        action="append",
        required=True,
    )
    parser.add_argument(
        "--max-workers",
        dest="max_workers",
        type=int,
        default=8,
        help="Maximum number of parallel workers (default: 8)"
    )
    parser.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        default=100,
        help="Number of items to process in each batch (default: 100)"
    )
    parser.add_argument(
        "--rate-limit",
        dest="rate_limit",
        type=int,
        default=10,
        help="Maximum API requests per second (default: 10)"
    )

    args = parser.parse_args()
    
    # Validate that --pc-source-id and --pc-published-wires are not used together
    if args.pc_source_id and args.pc_published_wires:
        parser.error(
            "--pc-source-id and --pc-published-wires cannot be used together. Use one or the other."
        )
    
    # Validate that either image-arc-id is provided, or both start-date and end-date are provided together
    if not args.image_arc_id and (bool(args.start_date) != bool(args.end_date)):
        parser.error(
            "either provide image-arc-id, or provide both start-date and end-date together (both are required if using date filtering)"
        )
    
    # Store original date values for processing
    start_date_str = args.start_date
    end_date_str = args.end_date
    
    # Initialize date values
    args.start_date = 0
    args.end_date = 0
    
    if start_date_str and end_date_str:
        # reformat dates
        element = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        timestamp = datetime.datetime.timestamp(element)
        args.start_date = int(timestamp) * 1000

        element = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
        timestamp = datetime.datetime.timestamp(element)
        args.end_date = int(timestamp) * 1000

    # Modify org based on environment
    org_with_env = args.org
    if args.environment == "sandbox":
        org_with_env = f"sandbox.{args.org}"
    
    arc_auth_header = {"Authorization": f"Bearer {args.bearer_token}"}
    pprint.pp(args)

    with PerformanceBenchmark("Total Combined Script Execution"):
        analysis = CombinedPhotoAnalysis(
            org=org_with_env,
            arc_auth_header=arc_auth_header,
            image_arc_id=args.image_arc_id,
            start_date=args.start_date,
            end_date=args.end_date,
            offset=args.offset,
            source=args.pc_source_id,
            website_list=args.website_list,
            max_workers=args.max_workers,
            batch_size=args.batch_size,
            rate_limit=args.rate_limit,
            pc_published_wires=args.pc_published_wires
        )
        analysis.doit()
    
    return 0


if __name__ == "__main__":
    exit(main()) 