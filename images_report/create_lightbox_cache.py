import argparse
import hashlib
import json
import math
import pprint
import sqlite3
import time
from typing import List, Dict, Any

import arrow
import requests
import tqdm
from jmespath import search
from decouple import config

from utils import (
    setup_logging, 
    benchmark, 
    RateLimiter, 
    get_db_path,
    format_duration,
    PerformanceBenchmark
)

LIGHTBOX_URL = "https://api.{}.arcpublishing.com/photo/api/v2/lightboxes?limit=100&offset={}"
LIGHTBOX_PHOTO_URL = "https://api.{}.arcpublishing.com/photo/api/v2/lightboxes/{}/photos"
LIGHTBOX_SINGLE_URL = "https://api.{}.arcpublishing.com/photo/api/v2/lightboxes/{}"


class LightboxCache:
    def __init__(
        self,
        org: str,
        arc_auth_header: Dict[str, str],
        max_workers: int = 8,
        rate_limit: int = 10
    ):
        self.arc_auth_header = arc_auth_header
        self.org = org
        self.org_for_filename = org.replace('sandbox.','')
        self.lightbox_total = None
        self.empty_lightboxes = []
        self.max_workers = max_workers
        self.rate_limiter = RateLimiter(rate_limit)
        self.logger = setup_logging(f"{self.org_for_filename}_lightbox_cache")
        
        # Statistics for benchmarking
        self.stats = {
            "total_lightboxes_processed": 0,
            "total_photos_processed": 0,
            "empty_lightboxes": 0,
            "api_calls": 0,
            "start_time": time.time()
        }
        
        # Database setup
        if "sandbox." in self.org:
            db_name = config("LIGHTBOX_CACHE_DB_SANDBOX", default="lightbox_photo_cache_sandbox.db")
        else:
            db_name = config("LIGHTBOX_CACHE_DB", default="lightbox_photo_cache.db")
        db_name = f"{self.org_for_filename}_{db_name}"

        db_path = get_db_path(db_name)
        self.logger.info(f"Connecting to database: {db_path}")
        
        # Connect to an SQLite database (or create it if it doesn't exist)
        self.conn = sqlite3.connect(db_path)
        
        # For visual progress bar
        self.pbar = None

    @benchmark
    def load_one_lightbox(self, lightbox_id: str) -> List[str]:
        """Load a single lightbox into the cache"""
        self.logger.info(f"Loading single lightbox {lightbox_id}")
        
        self.cache_db()
        
        self.rate_limiter.wait_if_needed()
        res = requests.get(
            LIGHTBOX_SINGLE_URL.format(self.org, lightbox_id), 
            headers=self.arc_auth_header, 
            timeout=30
        )
        self.stats["api_calls"] += 1
        
        if res.ok:
            results = res.json()
            # last_photo_added is not returned from the API endpoint that brings back a single lightbox,
            # so we won't compute and store the sha1. also won't store offset since it doesn't apply.
            self.load_lightbox(results["id"], "", "")
            self.load_lightbox_photos(results["id"])
            self.stats["total_lightboxes_processed"] += 1
            self.logger.info(f"Successfully loaded single lightbox {lightbox_id}")
        else:
            self.logger.error(f"Failed to load lightbox {lightbox_id}: {res.status_code}")
            
        return self.empty_lightboxes

    @benchmark
    def load_all_lightboxes(self, offset: int = 0) -> List[str]:
        """Load all lightboxes with pagination support"""
        self.cache_db()
        
        self.rate_limiter.wait_if_needed()
        res = requests.get(
            LIGHTBOX_URL.format(self.org, offset), 
            headers=self.arc_auth_header, 
            timeout=30
        )
        self.stats["api_calls"] += 1
        
        # save the offset parameter in db so you know how far you got if process ends too early
        self.update_offset(offset, arrow.utcnow().format("YYYY-MM-DD HH:mm:SS.SSS"))

        if res.ok:
            results = res.json()

            if not self.lightbox_total:
                self.lightbox_total = int(res.headers["X-Results-Total"])
                self.logger.info(
                    f"Found {self.lightbox_total} lightboxes, {math.ceil(self.lightbox_total/100)} pages of 100 items per page"
                )
                self.pbar = tqdm.tqdm(total=self.lightbox_total)

            elif offset + 100 <= self.lightbox_total:
                # the self.pbar gives feedback here
                pass
            else:
                self.logger.info("Done loading lightboxes")
                self.pbar.close()

            if results:
                for item in results:
                    self.pbar.update(1)

                    # generate hash to save in db, hash can be compared to determine if lightbox has changed
                    # turns the lightbox.last_photo_added dictionary into a single string
                    # if need to determine if lightbox has been altered, query value again, turn into string and compare with stored version
                    sha1_source_str = json.dumps(item.get("last_photo_added", None), sort_keys=True).encode("utf-8")
                    sha1 = hashlib.sha1(sha1_source_str).hexdigest()

                    # load lightbox into db cache
                    self.load_lightbox(item["id"], sha1, offset)
                    # load photos into db cache
                    self.load_lightbox_photos(item["id"])
                    
                    self.stats["total_lightboxes_processed"] += 1

                # process next page
                self.load_all_lightboxes(offset=offset + 100)
                # limits the process to a small subset for testing use, comment out line above and uncomment if statement below
                # if offset <= 100:
                #     self.load_all_lightboxes(offset=offset+100)
        else:
            self.logger.error(f"Failed to load lightboxes: {res.status_code} - {res.text}")
            
        return self.empty_lightboxes

    def load_lightbox(self, lightbox_id: str, sha1: str, offset: str) -> None:
        """Add lightbox to database cache"""
        self.add_lightbox((lightbox_id, sha1, offset, arrow.utcnow().format("YYYY-MM-DD HH:mm:SS.SSS")))
        return

    def load_lightbox_photos(self, lightbox_id: str) -> None:
        """Load photos for a specific lightbox"""
        self.rate_limiter.wait_if_needed()
        res = requests.get(
            LIGHTBOX_PHOTO_URL.format(self.org, lightbox_id), 
            headers=self.arc_auth_header, 
            timeout=30
        )
        self.stats["api_calls"] += 1
        
        if res.ok:
            results = res.json()
            photo_ids = search("[]._id", results)
            if photo_ids:
                for photo in photo_ids:
                    self.add_photo((photo, lightbox_id, arrow.utcnow().format("YYYY-MM-DD HH:mm:SS.SSS")))
                self.stats["total_photos_processed"] += len(photo_ids)
            else:
                self.empty_lightboxes.append(lightbox_id)
                self.stats["empty_lightboxes"] += 1
        else:
            self.logger.error(f"Failed to load photos for lightbox {lightbox_id}: {res.status_code}")
        return

    def cache_db(self) -> None:
        """Create database tables if they don't exist"""
        # Create tables
        lightbox_table_sql = """CREATE TABLE IF NOT EXISTS lightbox_cache (
            lightbox_id  STRING   CONSTRAINT lightbox_id_constraint UNIQUE ON CONFLICT REPLACE
                                  NOT NULL,
            sha1               STRING,
            offset_value       STRING,
            updated_date DATETIME NOT NULL
        ); """
        lightbox_photo_table_sql = """CREATE TABLE IF NOT EXISTS lightbox_photo_cache (
            photo_id        STRING   CONSTRAINT photo_id_constraint UNIQUE ON CONFLICT REPLACE
                                     NOT NULL,
            lightbox_id   STRING,
            updated_date    DATETIME NOT NULL
        ); """
        offset_table_sql = """CREATE TABLE IF NOT EXISTS offset_cache (
            last_offset    STRING   NOT NULL,
            updated_date    DATETIME NOT NULL
        );"""
        
        try:
            c = self.conn.cursor()
            c.execute(lightbox_table_sql)
        except sqlite3.Error as e:
            self.logger.error(f"Error creating lightbox table: {e}")

        try:
            # Create a cursor object using the cursor() method
            c = self.conn.cursor()
            c.execute(offset_table_sql)
        except sqlite3.Error as e:
            self.logger.error(f"Error creating offset table: {e}")

        try:
            # Create a cursor object using the cursor() method
            c = self.conn.cursor()
            c.execute(lightbox_photo_table_sql)
        except sqlite3.Error as e:
            self.logger.error(f"Error creating lightbox photo table: {e}")
        return

    def add_lightbox(self, lightbox: tuple) -> int:
        """Add lightbox to database"""
        sql = """ INSERT INTO lightbox_cache(lightbox_id, sha1, offset_value, updated_date) 
                  VALUES (?, ?, ?, ?) """
        # Create a cursor object using the cursor() method
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql, lightbox)
        except Exception as e:
            sql = """ UPDATE lightbox_cache SET sha1 = ?, offset_value = ?, updated_date = ? WHERE lightbox_id = ? """
            cursor.execute(sql, (lightbox[1], lightbox[2], lightbox[3], lightbox[0]))
        self.conn.commit()
        return cursor.lastrowid

    def add_photo(self, lightbox_photo: tuple) -> int:
        """Add photo to database"""
        sql = """ INSERT INTO lightbox_photo_cache(photo_id, lightbox_id, updated_date) 
                  VALUES (?, ?, ?) """
        # Create a cursor object using the cursor() method
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql, lightbox_photo)
        except Exception as e:
            sql = """ UPDATE lightbox_photo_cache SET lightbox_id = ?, updated_date = ? WHERE photo_id = ? """
            cursor.execute(sql, (lightbox_photo[1], lightbox_photo[2], lightbox_photo[0]))
        self.conn.commit()
        return cursor.lastrowid

    def update_offset(self, offset: int, update_date: str) -> int:
        """Update offset in database"""
        # Create a cursor object using the cursor() method
        cursor = self.conn.cursor()

        sql = """ DELETE FROM offset_cache"""
        cursor.execute(sql)

        sql = """ INSERT INTO offset_cache(last_offset, updated_date) VALUES (?, ?)"""
        cursor.execute(sql, (offset, update_date))

        self.conn.commit()
        return cursor.lastrowid

    def print_statistics(self) -> None:
        """Print processing statistics"""
        duration = time.time() - self.stats["start_time"]
        
        self.logger.info("=" * 50)
        self.logger.info(f"LIGHTBOX CACHE STATISTICS {self.org.upper()}")
        self.logger.info("=" * 50)
        self.logger.info(f"Total lightboxes processed: {self.stats['total_lightboxes_processed']}")
        self.logger.info(f"Total photos processed: {self.stats['total_photos_processed']}")
        self.logger.info(f"Empty lightboxes: {self.stats['empty_lightboxes']}")
        self.logger.info(f"Total API calls: {self.stats['api_calls']}")
        self.logger.info(f"Processing time: {format_duration(duration)}")
        if self.stats['total_lightboxes_processed'] > 0:
            self.logger.info(f"Average time per lightbox: {duration/self.stats['total_lightboxes_processed']:.3f}s")
        self.logger.info("=" * 50)


def main():
    """Main function to run the lightbox cache creation script"""
    parser = argparse.ArgumentParser(description="Create a cache of lightbox data for photo analysis")
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
    parser.add_argument(
        "--lightbox-id",
        dest="lightbox_id",
        help="a single lightbox id to load into cache, optional",
        required=False
    )
    parser.add_argument(
        "--offset",
        dest="offset",
        default=0,
        help="pass offset value to start the lightbox query at a specific point, rather than from the beginning",
    )
    parser.add_argument(
        "--max-workers",
        dest="max_workers",
        type=int,
        default=8,
        help="Maximum number of parallel workers (default: 8)"
    )
    parser.add_argument(
        "--rate-limit",
        dest="rate_limit",
        type=int,
        default=10,
        help="Maximum API requests per second (default: 10)"
    )
    
    args = parser.parse_args()
    
    # Modify org based on environment
    org_with_env = args.org
    if args.environment == "sandbox":
        org_with_env = f"sandbox.{args.org}"
    
    arc_auth_header = {"Authorization": f"Bearer {args.bearer_token}"}
    pprint.pp(args)

    with PerformanceBenchmark("Total Lightbox Cache Creation"):
        cache_lightboxes = LightboxCache(
            org=org_with_env, 
            arc_auth_header=arc_auth_header,
            max_workers=args.max_workers,
            rate_limit=args.rate_limit
        )
        
        if args.lightbox_id:
            empty_lightboxes = cache_lightboxes.load_one_lightbox(lightbox_id=args.lightbox_id)
        else:
            empty_lightboxes = cache_lightboxes.load_all_lightboxes(offset=args.offset)
            
        cache_lightboxes.print_statistics()
        print(f"Empty lightboxes: {empty_lightboxes}")
    
    return 0


if __name__ == "__main__":
    exit(main()) 