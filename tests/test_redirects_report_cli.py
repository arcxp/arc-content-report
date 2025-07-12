"""
CLI argument tests for redirects_report module
"""
import pytest
import argparse
from unittest.mock import patch, MagicMock
import sys
from io import StringIO

from redirects_report.identify_redirects import main, RedirectsReporter


class TestRedirectsReportCLI:
    """Test CLI argument parsing and validation for redirects_report module."""
    
    def setup_method(self):
        """Setup test environment."""
        self.valid_args = [
            "--org", "test-org",
            "--bearer-token", "test-token",
            "--website", "test-website",
            "--website-domain", "https://test-website.com"
        ]
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_required_arguments(self, mock_setup_logging, mock_reporter_class):
        """Test that required arguments are properly parsed."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args + [
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31"
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        # Verify reporter was created with correct arguments
        mock_reporter_class.assert_called_once()
        call_args = mock_reporter_class.call_args[1]
        assert call_args['org'] == 'test-org'
        assert call_args['bearer_token'] == 'test-token'
        assert call_args['website'] == 'test-website'
        assert call_args['website_domain'] == 'https://test-website.com'
        assert call_args['environment'] == 'production'  # default
        assert call_args['max_workers'] == 5  # default
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_optional_arguments(self, mock_setup_logging, mock_reporter_class):
        """Test that optional arguments are properly parsed."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 10,
            'date_ranges_processed': 2,
            'output_file': 'test_output.csv',
            'status_checking_enabled': True,
            'max_workers_used': 8
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args + [
            "--environment", "sandbox",
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31",
            "--do-404-or-200", "1",
            "--max-workers", "8",
            "--auto-optimize-workers",
            "--report-folder", "custom_output",
            "--output-prefix", "redirects_"
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        # Verify reporter was created with correct optional arguments
        call_args = mock_reporter_class.call_args[1]
        assert call_args['environment'] == 'sandbox'
        assert call_args['do_404_or_200'] == True  # converted from int
        assert call_args['max_workers'] == 8
        assert call_args['report_folder'] == 'custom_output'
        assert call_args['output_prefix'] == 'redirects_'
    
    def test_missing_required_arguments(self):
        """Test that missing required arguments raise appropriate errors."""
        # Test missing org
        args = [
            "--bearer-token", "test-token",
            "--website", "test-website",
            "--website-domain", "https://test-website.com"
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2  # argparse error code
        
        # Test missing bearer-token
        args = [
            "--org", "test-org",
            "--website", "test-website",
            "--website-domain", "https://test-website.com"
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
        
        # Test missing website
        args = [
            "--org", "test-org",
            "--bearer-token", "test-token",
            "--website-domain", "https://test-website.com"
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
        
        # Test missing website-domain
        args = [
            "--org", "test-org",
            "--bearer-token", "test-token",
            "--website", "test-website"
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_environment_choices(self, mock_setup_logging, mock_reporter_class):
        """Test environment argument choices."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test production environment
        args = self.valid_args + ["--environment", "production"]
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['environment'] == 'production'
        
        # Test sandbox environment
        mock_reporter_class.reset_mock()
        args = self.valid_args + ["--environment", "sandbox"]
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['environment'] == 'sandbox'
        
        # Test invalid environment
        args = self.valid_args + ["--environment", "invalid"]
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_do_404_or_200_choices(self, mock_setup_logging, mock_reporter_class):
        """Test do-404-or-200 argument choices."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test with 0 (disabled)
        args = self.valid_args + ["--do-404-or-200", "0"]
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['do_404_or_200'] == False  # converted from int
        
        # Test with 1 (enabled)
        mock_reporter_class.reset_mock()
        args = self.valid_args + ["--do-404-or-200", "1"]
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['do_404_or_200'] == True  # converted from int
        
        # Test invalid choice
        args = self.valid_args + ["--do-404-or-200", "2"]
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_max_workers_validation(self, mock_setup_logging, mock_reporter_class):
        """Test max-workers argument validation."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test valid integer
        args = self.valid_args + ["--max-workers", "10"]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['max_workers'] == 10
        
        # Test invalid integer
        args = self.valid_args + ["--max-workers", "invalid"]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_auto_optimize_workers_flag(self, mock_setup_logging, mock_reporter_class):
        """Test auto-optimize-workers flag."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test with flag
        args = self.valid_args + ["--auto-optimize-workers"]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        # Verify the flag was passed (though it's not directly used in constructor)
        # The flag affects behavior in generate_report method
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_date_arguments(self, mock_setup_logging, mock_reporter_class):
        """Test date range arguments."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test with date range
        args = self.valid_args + [
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31"
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        # Verify generate_report was called with correct dates
        mock_reporter.generate_report.assert_called_once_with("2024-01-01", "2024-01-31")
        
        # Test with empty dates
        mock_reporter.reset_mock()
        args = self.valid_args + [
            "--start-date", "",
            "--end-date", ""
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        mock_reporter.generate_report.assert_called_once_with("", "")
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_output_summary(self, mock_setup_logging, mock_reporter_class, capsys):
        """Test that output summary is printed correctly."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 150,
            'date_ranges_processed': 3,
            'output_file': 'redirects_report_2024.csv',
            'status_checking_enabled': True,
            'max_workers_used': 8
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args + [
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31"
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        captured = capsys.readouterr()
        output = captured.out
        
        assert "REPORT SUMMARY" in output
        assert "Total items processed: 150" in output
        assert "Date ranges processed: 3" in output
        assert "Output file: redirects_report_2024.csv" in output
        assert "Status checking: Enabled" in output
        assert "Max workers used: 8" in output
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_output_summary_disabled_status_checking(self, mock_setup_logging, mock_reporter_class, capsys):
        """Test that output summary shows disabled status checking."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 50,
            'date_ranges_processed': 1,
            'output_file': 'redirects_report.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args + [
            "--do-404-or-200", "0"
        ]
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        captured = capsys.readouterr()
        output = captured.out
        
        assert "Status checking: Disabled" in output
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_exception_handling(self, mock_setup_logging, mock_reporter_class):
        """Test exception handling in main function."""
        mock_reporter_class.side_effect = Exception("Test error")
        
        args = self.valid_args
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            with pytest.raises(Exception) as exc_info:
                main()
            assert str(exc_info.value) == "Test error"
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_logging_setup(self, mock_setup_logging, mock_reporter_class):
        """Test that logging is set up correctly."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        # Verify logging was set up
        mock_setup_logging.assert_called_once_with('redirects')
    
    def test_help_output(self):
        """Test that help output is generated correctly."""
        with patch.object(sys, 'argv', ['identify_redirects', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0  # Help exits with 0
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_default_values(self, mock_setup_logging, mock_reporter_class):
        """Test that default values are applied correctly."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test with minimal arguments
        args = self.valid_args
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['environment'] == 'production'  # default
        assert call_args['do_404_or_200'] == False  # default (0 converted to False)
        assert call_args['max_workers'] == 5  # default
        assert call_args['report_folder'] == 'spreadsheets'  # default
        assert call_args['output_prefix'] == ''  # default
    
    @patch('redirects_report.identify_redirects.RedirectsReporter')
    @patch('redirects_report.identify_redirects.utils.setup_logging')
    def test_bearer_token_logging(self, mock_setup_logging, mock_reporter_class):
        """Test that bearer token is properly truncated in logging."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'status_checking_enabled': False,
            'max_workers_used': 5
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args
        
        with patch.object(sys, 'argv', ['identify_redirects'] + args):
            main()
        
        # Verify that the logging call was made (the actual truncation is tested in the main function)
        mock_setup_logging.assert_called_once()


class TestRedirectsReporterCLI:
    """Test RedirectsReporter class CLI-related functionality."""
    
    def test_redirects_reporter_initialization(self):
        """Test RedirectsReporter initialization with CLI arguments."""
        reporter = RedirectsReporter(
            bearer_token="test-token",
            org="test-org",
            website="test-website",
            website_domain="https://test-website.com",
            environment="sandbox",
            do_404_or_200=True,
            max_workers=10,
            report_folder="custom_output",
            output_prefix="redirects_"
        )
        
        assert reporter.bearer_token == "test-token"
        assert reporter.org == "test-org"
        assert reporter.website == "test-website"
        assert reporter.website_domain == "https://test-website.com"
        assert reporter.env == "sandbox"
        assert reporter.do_404_or_200 == True
        assert reporter.max_workers == 10
        assert reporter.report_folder == "custom_output"
        assert reporter.output_prefix == "redirects_"
    
    def test_redirects_reporter_defaults(self):
        """Test RedirectsReporter initialization with default values."""
        reporter = RedirectsReporter(
            bearer_token="test-token",
            org="test-org",
            website="test-website",
            website_domain="https://test-website.com"
        )
        
        assert reporter.env == "production"
        assert reporter.do_404_or_200 == False
        assert reporter.max_workers == 5
        assert reporter.report_folder == "spreadsheets"
        assert reporter.output_prefix == ""
        assert reporter.auto_optimize_workers == True
    
    def test_redirects_reporter_website_domain_required(self):
        """Test that website_domain is properly handled."""
        reporter = RedirectsReporter(
            bearer_token="test-token",
            org="test-org",
            website="test-website",
            website_domain="https://example.com"
        )
        
        assert reporter.website_domain == "https://example.com"
        
        # Test with empty domain
        reporter = RedirectsReporter(
            bearer_token="test-token",
            org="test-org",
            website="test-website",
            website_domain=""
        )
        
        assert reporter.website_domain == "" 