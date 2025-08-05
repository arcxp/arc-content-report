"""
Arc XP Wires Reports Script
Integrates date range automation and parallel processing for wires content
"""
import argparse
import logging
from typing import List, Dict, Any, Optional

import utils
import daterange_builder
from .identify_wires_parallel_processor import WiresParallelProcessor, optimize_worker_count

logger = logging.getLogger(__name__)

class WiresReporter:
    """Wires reporter """
    
    def __init__(
        self,
        bearer_token: str,
        org: str,
        environment: str = "production",
        website: str = "",
        q_extra_filters : str = "",
        report_folder: str = "spreadsheets",
        output_prefix: str = "",
        max_workers: int = 5,
        auto_optimize_workers: bool = True,
        q_extra_fields: Optional[List[str]] = None
    ):
        self.bearer_token = bearer_token
        self.org = org
        self.env = environment
        self.website = website
        self.q_extra_filters = q_extra_filters
        self.report_folder = report_folder
        self.output_prefix = output_prefix
        self.max_workers = max_workers
        self.auto_optimize_workers = auto_optimize_workers
        self.q_extra_fields = q_extra_fields or []
        # Setup logging
        utils.setup_logging(f"{self.org}_wires")
        # Initialize components
        self.date_builder = daterange_builder.DateRangeBuilder(bearer_token, org, website, environment)
        self.parallel_processor = WiresParallelProcessor(
            bearer_token, org, website, environment, max_workers, self.q_extra_fields
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
                date_ranges[:3], self.bearer_token, self.org, self.website, self.env, self.q_extra_filters
            )
            self.parallel_processor.max_workers = optimal_workers
            logger.info(f"Optimized worker count: {optimal_workers}")
        
        return self.parallel_processor.process_ranges_parallel(date_ranges, self.q_extra_filters)
    
    @utils.timing_decorator
    def export_results(self, data: List[Dict[str, Any]], start_date: str, end_date: str) -> str:
        """Export results to CSV."""
        if not data:
            logger.warning("No data to export")
            return ""
        
        return self.parallel_processor.export_to_csv(
            data, start_date, end_date, self.report_folder, self.output_prefix, self.q_extra_filters
        )
    
    def generate_report(self, start_date: str = "", end_date: str = "") -> Dict[str, Any]:
        """
        Generate comprehensive wires report.
        
        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            q_extra_filters: Additional query parameters to filter results
            
        Returns:
            Report summary dictionary
        """
        logger.info(f"Starting wires report generation")
        logger.info(f"Environment: {self.env.upper()}")
        logger.info(f"Website: {self.website}")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Additional query: {self.q_extra_filters}")
        
        # Step 1: Build optimal date ranges
        date_ranges = self.build_optimal_date_ranges(start_date, end_date)
        
        # Step 2: Process date ranges in parallel
        data = self.process_date_ranges(date_ranges)
        
        # Step 3: Export results
        output_file = self.export_results(data, start_date, end_date)
        
        # Generate summary
        summary = {
            "total_items": len(data),
            "date_ranges_processed": len(date_ranges),
            "output_file": output_file,
            "max_workers_used": self.parallel_processor.max_workers,
            "additional_query": self.q_extra_filters
        }
        
        logger.info(f"Report generation completed. Summary: {summary}")
        return summary

def main():
    """Main entry point for wires report."""
    parser = argparse.ArgumentParser(description="Arc XP Wires Report")
    
    # Required arguments
    parser.add_argument("--org", required=True, help="Arc XP organization ID")
    parser.add_argument("--bearer-token", required=True, help="API bearer token")
    parser.add_argument("--website", required=True, help="Website identifier")
    
    # Optional arguments
    parser.add_argument("--environment", default="production", choices=["production", "sandbox"], 
                       help="Environment (production/sandbox)")
    parser.add_argument("--start-date", default="", help="Start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    parser.add_argument("--end-date", default="", help="End date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    parser.add_argument("--q-extra-filters", default="", help="Optional additional query parameters to filter results, must be within quotation marks")
    parser.add_argument("--q-extra-fields", default="", help="Comma-separated list of extra ANS fields to include in _sourceInclude")
    parser.add_argument("--max-workers", type=int, default=5, help="Maximum parallel workers")
    parser.add_argument("--auto-optimize-workers", action="store_true", 
                       help="Automatically optimize worker count")
    parser.add_argument("--report-folder", default="spreadsheets", help="Output directory")
    parser.add_argument("--output-prefix", default="", help="Prefix string for output filename")

    args = parser.parse_args()
    
    # Setup logging
    utils.setup_logging(f'{args.org}_wires')
    logger.info("Starting wires report")

    # don't log full bearer token, truncate it instead
    args_copy = vars(args).copy()
    args_copy["bearer_token"] = str(args_copy["bearer_token"])[6:]  # Only show first 6 chars for privacy
    logger.info(f"Arguments: {args_copy}")
    
    # Parse extra fields
    q_extra_fields = [f.strip() for f in args.q_extra_fields.split(",") if f.strip()] if args.q_extra_fields else []
    try:
        # Create reporter
        reporter = WiresReporter(
            bearer_token=args.bearer_token,
            org=args.org,
            environment=args.environment,
            website=args.website,
            q_extra_filters=args.q_extra_filters,
            report_folder=args.report_folder,
            output_prefix=args.output_prefix,
            max_workers=args.max_workers,
            q_extra_fields=q_extra_fields
        )
        
        # Generate report
        summary = reporter.generate_report(args.start_date, args.end_date)
        
        # Print summary
        print("\n" + "="*50)
        print("WIRES REPORT SUMMARY")
        print("="*50)
        print(f"Total wires found: {summary['total_items']}")
        print(f"Date ranges processed: {summary['date_ranges_processed']}")
        print(f"Output file: {summary['output_file']}")
        print(f"Max workers used: {summary['max_workers_used']}")
        if summary['additional_query']:
            print(f"Additional query: {summary['additional_query']}")
        print("="*50)
        
    except Exception as e:
        logger.error(f"Error generating wires report: {e}")
        raise

if __name__ == "__main__":
    main()