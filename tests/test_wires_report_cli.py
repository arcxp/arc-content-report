"""
CLI argument tests for wires_report module
"""
import pytest
import argparse
from unittest.mock import patch, MagicMock
import sys
from io import StringIO

from wires_report.identify_wires import main, WiresReporter


class TestWiresReportCLI:
    """Test CLI argument parsing and validation for wires_report module."""
    
    def setup_method(self):
        """Setup test environment."""
        self.valid_args = [
            "--org", "test-org",
            "--bearer-token", "test-token",
            "--website", "test-website"
        ]
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_required_arguments(self, mock_setup_logging, mock_reporter_class):
        """Test that required arguments are properly parsed."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'max_workers_used': 5,
            'additional_query': ''
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args + [
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31"
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        # Verify reporter was created with correct arguments
        mock_reporter_class.assert_called_once()
        call_args = mock_reporter_class.call_args[1]
        assert call_args['org'] == 'test-org'
        assert call_args['bearer_token'] == 'test-token'
        assert call_args['website'] == 'test-website'
        assert call_args['environment'] == 'production'  # default
        assert call_args['max_workers'] == 5  # default
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_optional_arguments(self, mock_setup_logging, mock_reporter_class):
        """Test that optional arguments are properly parsed."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 10,
            'date_ranges_processed': 2,
            'output_file': 'test_output.csv',
            'max_workers_used': 8,
            'additional_query': 'source.name:AP'
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args + [
            "--environment", "sandbox",
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31",
            "--q-extra-filters", "source.name:AP",
            "--q-extra-fields", "distributor.name,source.system",
            "--max-workers", "8",
            "--auto-optimize-workers",
            "--report-folder", "custom_output",
            "--output-prefix", "wires_"
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        # Verify reporter was created with correct optional arguments
        call_args = mock_reporter_class.call_args[1]
        assert call_args['environment'] == 'sandbox'
        assert call_args['q_extra_filters'] == 'source.name:AP'
        assert call_args['q_extra_fields'] == ['distributor.name', 'source.system']
        assert call_args['max_workers'] == 8
        assert call_args['report_folder'] == 'custom_output'
        assert call_args['output_prefix'] == 'wires_'
    
    def test_missing_required_arguments(self):
        """Test that missing required arguments raise appropriate errors."""
        # Test missing org
        args = [
            "--bearer-token", "test-token",
            "--website", "test-website"
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2  # argparse error code
        
        # Test missing bearer-token
        args = [
            "--org", "test-org",
            "--website", "test-website"
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
        
        # Test missing website
        args = [
            "--org", "test-org",
            "--bearer-token", "test-token"
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_environment_choices(self, mock_setup_logging, mock_reporter_class):
        """Test environment argument choices."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'max_workers_used': 5,
            'additional_query': ''
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test production environment
        args = self.valid_args + ["--environment", "production"]
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['environment'] == 'production'
        
        # Test sandbox environment
        mock_reporter_class.reset_mock()
        args = self.valid_args + ["--environment", "sandbox"]
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['environment'] == 'sandbox'
        
        # Test invalid environment
        args = self.valid_args + ["--environment", "invalid"]
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_q_extra_fields_parsing(self, mock_setup_logging, mock_reporter_class):
        """Test parsing of q-extra-fields argument."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'max_workers_used': 5,
            'additional_query': ''
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test with extra fields
        args = self.valid_args + [
            "--q-extra-fields", "distributor.name,source.system,content_restrictions"
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['q_extra_fields'] == ['distributor.name', 'source.system', 'content_restrictions']
        
        # Test with empty extra fields
        mock_reporter_class.reset_mock()
        args = self.valid_args + ["--q-extra-fields", ""]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['q_extra_fields'] == []
        
        # Test with whitespace in extra fields
        mock_reporter_class.reset_mock()
        args = self.valid_args + [
            "--q-extra-fields", " field1 , field2 , field3 "
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['q_extra_fields'] == ['field1', 'field2', 'field3']
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_max_workers_validation(self, mock_setup_logging, mock_reporter_class):
        """Test max-workers argument validation."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'max_workers_used': 5,
            'additional_query': ''
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test valid integer
        args = self.valid_args + ["--max-workers", "10"]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['max_workers'] == 10
        
        # Test invalid integer
        args = self.valid_args + ["--max-workers", "invalid"]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_auto_optimize_workers_flag(self, mock_setup_logging, mock_reporter_class):
        """Test auto-optimize-workers flag."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'max_workers_used': 5,
            'additional_query': ''
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test with flag
        args = self.valid_args + ["--auto-optimize-workers"]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        # Verify the flag was passed (though it's not directly used in constructor)
        # The flag affects behavior in generate_report method
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_date_arguments(self, mock_setup_logging, mock_reporter_class):
        """Test date range arguments."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'max_workers_used': 5,
            'additional_query': ''
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test with date range
        args = self.valid_args + [
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31"
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        # Verify generate_report was called with correct dates
        mock_reporter.generate_report.assert_called_once_with("2024-01-01", "2024-01-31")
        
        # Test with empty dates
        mock_reporter.reset_mock()
        args = self.valid_args + [
            "--start-date", "",
            "--end-date", ""
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        mock_reporter.generate_report.assert_called_once_with("", "")
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_output_summary(self, mock_setup_logging, mock_reporter_class, capsys):
        """Test that output summary is printed correctly."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 150,
            'date_ranges_processed': 3,
            'output_file': 'wires_report_2024.csv',
            'max_workers_used': 8,
            'additional_query': 'source.name:AP'
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args + [
            "--start-date", "2024-01-01",
            "--end-date", "2024-01-31"
        ]
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        captured = capsys.readouterr()
        output = captured.out
        
        assert "WIRES REPORT SUMMARY" in output
        assert "Total wires found: 150" in output
        assert "Date ranges processed: 3" in output
        assert "Output file: wires_report_2024.csv" in output
        assert "Max workers used: 8" in output
        assert "Additional query: source.name:AP" in output
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_exception_handling(self, mock_setup_logging, mock_reporter_class):
        """Test exception handling in main function."""
        mock_reporter_class.side_effect = Exception("Test error")
        
        args = self.valid_args
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            with pytest.raises(Exception) as exc_info:
                main()
            assert str(exc_info.value) == "Test error"
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_logging_setup(self, mock_setup_logging, mock_reporter_class):
        """Test that logging is set up correctly."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'max_workers_used': 5,
            'additional_query': ''
        }
        mock_reporter_class.return_value = mock_reporter
        
        args = self.valid_args
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        # Verify logging was set up
        mock_setup_logging.assert_called_once_with('wires')
    
    def test_help_output(self):
        """Test that help output is generated correctly."""
        with patch.object(sys, 'argv', ['identify_wires', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0  # Help exits with 0
    
    @patch('wires_report.identify_wires.WiresReporter')
    @patch('wires_report.identify_wires.utils.setup_logging')
    def test_default_values(self, mock_setup_logging, mock_reporter_class):
        """Test that default values are applied correctly."""
        mock_reporter = MagicMock()
        mock_reporter.generate_report.return_value = {
            'total_items': 0,
            'date_ranges_processed': 0,
            'output_file': 'test.csv',
            'max_workers_used': 5,
            'additional_query': ''
        }
        mock_reporter_class.return_value = mock_reporter
        
        # Test with minimal arguments
        args = self.valid_args
        
        with patch.object(sys, 'argv', ['identify_wires'] + args):
            main()
        
        call_args = mock_reporter_class.call_args[1]
        assert call_args['environment'] == 'production'  # default
        assert call_args['max_workers'] == 5  # default
        assert call_args['report_folder'] == 'spreadsheets'  # default
        assert call_args['output_prefix'] == ''  # default
        assert call_args['q_extra_filters'] == ''  # default
        assert call_args['q_extra_fields'] == []  # default


class TestWiresReporterCLI:
    """Test WiresReporter class CLI-related functionality."""
    
    def test_wires_reporter_initialization(self):
        """Test WiresReporter initialization with CLI arguments."""
        reporter = WiresReporter(
            bearer_token="test-token",
            org="test-org",
            website="test-website",
            environment="sandbox",
            q_extra_filters="source.name:AP",
            q_extra_fields=["field1", "field2"],
            max_workers=10,
            report_folder="custom_output",
            output_prefix="wires_"
        )
        
        assert reporter.bearer_token == "test-token"
        assert reporter.org == "test-org"
        assert reporter.website == "test-website"
        assert reporter.env == "sandbox"
        assert reporter.q_extra_filters == "source.name:AP"
        assert reporter.q_extra_fields == ["field1", "field2"]
        assert reporter.max_workers == 10
        assert reporter.report_folder == "custom_output"
        assert reporter.output_prefix == "wires_"
    
    def test_wires_reporter_defaults(self):
        """Test WiresReporter initialization with default values."""
        reporter = WiresReporter(
            bearer_token="test-token",
            org="test-org",
            website="test-website"
        )
        
        assert reporter.env == "production"
        assert reporter.q_extra_filters == ""
        assert reporter.q_extra_fields == []
        assert reporter.max_workers == 5
        assert reporter.report_folder == "spreadsheets"
        assert reporter.output_prefix == "" 