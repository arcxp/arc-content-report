"""
Optimized Arc XP org Redirect Reports Script
Integrates date range automation, parallel processing, and async status checking
"""
import argparse
import logging
import os
import pathlib
from typing import List, Dict, Any, Optional
from datetime import datetime

import utils # import setup_logging, timing_decorator, create_output_filename
import daterange_builder # import DateRangeBuilder, create_date_ranges_from_tuples
from .parallel_processor import ParallelProcessor, optimize_worker_count
from .status_checker import check_redirect_statuses_sync

logger = logging.getLogger(__name__)

class OptimizedRedirectReporter:
    """Optimized redirect reporter with all performance improvements."""
    
    def __init__(
        self,
        bearer_token: str,
        org: str,
        environment: str = "production",
        website: str = "",
        website_domain: str = "",
        do_404_or_200: bool = False,
        report_folder: str = "spreadsheets",
        output_prefix: str = "",
        max_workers: int = 5,
        auto_optimize_workers: bool = True
    ):
        self.bearer_token = bearer_token
        self.org = org
        self.env = environment
        self.website = website
        self.website_domain = website_domain
        self.do_404_or_200 = do_404_or_200
        self.report_folder = report_folder
        self.output_prefix = output_prefix
        self.max_workers = max_workers
        self.auto_optimize_workers = auto_optimize_workers
        
        # Setup logging
        utils.setup_logging()
        
        # Initialize components
        self.date_builder = daterange_builder.DateRangeBuilder(bearer_token, org, website, environment)
        self.parallel_processor = ParallelProcessor(
            bearer_token, org, website, environment, max_workers
        )
    
    @utils.timing_decorator
    def build_optimal_date_ranges(self, start_date: str, end_date: str) -> List[tuple]:
        """Build optimal date ranges for processing."""
        logger.info(f"Building optimal date ranges from {start_date} to {end_date}")
        
        if not start_date or not end_date:
            logger.info("No date range specified, using all dates")
            return []
        
        return self.date_builder.build_optimal_ranges(start_date, end_date)
    
    @utils.timing_decorator
    def process_date_ranges(self, date_ranges: List[tuple]) -> List[Dict[str, Any]]:
        """Process date ranges in parallel."""
        if not date_ranges:
            logger.warning("No date ranges to process")
            return []
        
        # Optimize worker count if requested
        if self.auto_optimize_workers and len(date_ranges) > 3:
            optimal_workers = optimize_worker_count(
                date_ranges[:3], self.bearer_token, self.org, self.website, self.env
            )
            self.parallel_processor.max_workers = optimal_workers
            logger.info(f"Optimized worker count: {optimal_workers}")
        
        return self.parallel_processor.process_ranges_parallel(date_ranges)
    
    @utils.timing_decorator
    def check_redirect_statuses(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check redirect statuses if requested."""
        if not self.do_404_or_200:
            logger.info("Skipping status checking (not requested)")
            return data
        
        if not self.website_domain:
            logger.warning("No website domain provided, skipping status checking")
            return data
        
        logger.info("Starting async status checking")
        return check_redirect_statuses_sync(data, self.website_domain)
    
    @utils.timing_decorator
    def export_results(self, data: List[Dict[str, Any]], start_date: str, end_date: str) -> str:
        """Export results to CSV."""
        if not data:
            logger.warning("No data to export")
            return ""
        
        return self.parallel_processor.export_to_csv(
            data, start_date, end_date, self.report_folder, self.output_prefix
        )
    
    def generate_report(self, start_date: str = "", end_date: str = "") -> Dict[str, Any]:
        """
        Generate comprehensive redirect report.
        
        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            
        Returns:
            Report summary dictionary
        """
        logger.info(f"Starting optimized redirect report generation")
        logger.info(f"Environment: {self.env.upper()}")
        logger.info(f"Website: {self.website}")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Status checking: {self.do_404_or_200}")
        
        # Step 1: Build optimal date ranges
        date_ranges = self.build_optimal_date_ranges(start_date, end_date)
        
        # Step 2: Process date ranges in parallel
        data = self.process_date_ranges(date_ranges)
        
        # Step 3: Check redirect statuses if requested
        data = self.check_redirect_statuses(data)
        
        # Step 4: Export results
        output_file = self.export_results(data, start_date, end_date)
        
        # Generate summary
        summary = {
            "total_items": len(data),
            "date_ranges_processed": len(date_ranges),
            "output_file": output_file,
            "status_checking_enabled": self.do_404_or_200,
            "max_workers_used": self.parallel_processor.max_workers
        }
        
        logger.info(f"Report generation completed. Summary: {summary}")
        return summary

def main():
    """Main entry point for optimized redirect identification."""
    parser = argparse.ArgumentParser(description="Optimized Arc XP Organization Redirects Report")
    
    # Required arguments
    parser.add_argument("--org", required=True, help="Arc XP organization ID")
    parser.add_argument("--bearer-token", required=True, help="API bearer token")
    parser.add_argument("--website", required=True, help="Website identifier")
    parser.add_argument("--website-domain", required=True, help="Website domain URL")
    
    # Optional arguments
    parser.add_argument("--environment", default="production", choices=["production", "sandbox"], 
                       help="Environment (production/sandbox)")
    parser.add_argument("--start-date", default="", help="Start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    parser.add_argument("--end-date", default="", help="End date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    parser.add_argument("--do-404-or-200", type=int, default=0, choices=[0, 1],
                       help="Check redirect status (0=no, 1=yes)")
    parser.add_argument("--max-workers", type=int, default=5, help="Maximum parallel workers")
    parser.add_argument("--auto-optimize-workers", action="store_true", 
                       help="Automatically optimize worker count")
    parser.add_argument("--report-folder", default="spreadsheets", help="Output directory")
    parser.add_argument("--output-prefix", default="", help="Prefix string for output filename")

    args = parser.parse_args()
    
    # Setup logging
    utils.setup_logging()
    logger.info("Starting optimized redirect identification")

    # don't log full bearer token, truncate it instead
    args_copy = vars(args).copy()
    args_copy["bearer_token"] = str(args_copy["bearer_token"])[:-65]
    logger.info(f"Arguments: {args_copy}")
    
    try:
        # Create reporter
        reporter = OptimizedRedirectReporter(
            bearer_token=args.bearer_token,
            org=args.org,
            environment=args.environment,
            website=args.website,
            website_domain=args.website_domain,
            do_404_or_200=bool(args.do_404_or_200),
            report_folder=args.report_folder,
            output_prefix=args.output_prefix,
            max_workers=args.max_workers,
            auto_optimize_workers=args.auto_optimize_workers
        )
        
        # Generate report
        summary = reporter.generate_report(args.start_date, args.end_date)
        
        # Print summary
        print("\n" + "="*50)
        print("REPORT SUMMARY")
        print("="*50)
        print(f"Total items processed: {summary['total_items']}")
        print(f"Date ranges processed: {summary['date_ranges_processed']}")
        print(f"Output file: {summary['output_file']}")
        print(f"Status checking: {'Enabled' if summary['status_checking_enabled'] else 'Disabled'}")
        print(f"Max workers used: {summary['max_workers_used']}")
        print("="*50)
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise

if __name__ == "__main__":
    main() 