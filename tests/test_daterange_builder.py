"""
Unit tests for daterange_builder module
"""
import pytest
import requests
import logging
from unittest.mock import Mock, patch
import sys
import os

# Add the parent directory to the Python path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import daterange_builder


class TestDateRangeBuilder:
    """Test cases for DateRangeBuilder class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.builder = daterange_builder.DateRangeBuilder(
            bearer_token="test_token",
            org="test_org",
            website="test_website",
            environment="sandbox"
        )

    @patch('daterange_builder.requests.get')
    def test_get_total_hits_success(self, mock_get):
        """Test successful total hits retrieval."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {"count": 5000}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.builder.get_total_hits("2020-01-01", "2020-01-31")

        assert result == 5000
        mock_get.assert_called_once()

    @patch('daterange_builder.requests.get')
    def test_get_total_hits_failure(self, mock_get):
        """Test failed total hits retrieval."""
        mock_get.side_effect = requests.exceptions.RequestException("API Error")

        result = self.builder.get_total_hits("2020-01-01", "2020-01-31")

        assert result == 0

    def test_validate_date_range_valid(self):
        """Test valid date range validation."""
        result = self.builder.validate_date_range("2020-01-01", "2020-01-31")
        assert result is True

    def test_validate_date_range_invalid(self):
        """Test invalid date range validation."""
        result = self.builder.validate_date_range("2020-01-31", "2020-01-01")
        assert result is False

    def test_validate_date_range_malformed(self):
        """Test malformed date range validation."""
        result = self.builder.validate_date_range("invalid-date", "2020-01-31")
        assert result is False

    @patch.object(daterange_builder.DateRangeBuilder, 'get_total_hits')
    def test_split_range_within_limits(self, mock_get_hits):
        """Test date range splitting when within API limits."""
        mock_get_hits.return_value = 8000  # Within 10k limit

        result = self.builder.split_range("2020-01-01", "2020-01-31")

        assert result == [("2020-01-01", "2020-01-31")]
        mock_get_hits.assert_called_once_with("2020-01-01", "2020-01-31")

    @patch.object(daterange_builder.DateRangeBuilder, 'get_total_hits')
    def test_split_range_exceeds_limits(self, mock_get_hits):
        """Test date range splitting when exceeding API limits."""
        # First call exceeds limit, subsequent calls are within limit
        mock_get_hits.side_effect = [20000, 8000, 8000]

        result = self.builder.split_range("2020-01-01", "2020-01-31")

        # Should return two ranges after splitting
        assert len(result) == 2
        assert mock_get_hits.call_count == 3

    @patch.object(daterange_builder.DateRangeBuilder, 'get_total_hits')
    def test_split_range_max_recursion(self, mock_get_hits):
        """Test date range splitting with max recursion depth."""
        # Always exceed limits to trigger recursion
        mock_get_hits.return_value = 20000

        result = self.builder.split_range("2020-01-01", "2020-01-31", depth=10)

        # Should return original range when max depth reached
        assert result == [("2020-01-01", "2020-01-31")]

    @patch.object(daterange_builder.DateRangeBuilder, 'build_optimal_ranges')
    def test_create_date_ranges_from_tuples(self, mock_build_ranges):
        """Test creating date ranges from tuples."""
        mock_build_ranges.return_value = [("2020-01-01", "2020-01-15"), ("2020-01-16", "2020-01-31")]

        date_tuples = [("2020-01-01", "2020-01-31")]
        result = daterange_builder.create_date_ranges_from_tuples(
            date_tuples, "test_token", "test_org", "test_website", "sandbox"
        )

        assert len(result) == 2
        assert result == [("2020-01-01", "2020-01-15"), ("2020-01-16", "2020-01-31")]


class TestDateRangeBuilderIntegration:
    """Integration tests for DateRangeBuilder."""

    def test_build_optimal_ranges_logging(self, caplog):
        """Test that build_optimal_ranges logs appropriately."""
        caplog.set_level(logging.INFO)
        with patch.object(daterange_builder.DateRangeBuilder, 'get_total_hits', return_value=5000):
            builder = daterange_builder.DateRangeBuilder("test_token", "test_org", "test_website")
            result = builder.build_optimal_ranges("2020-01-01", "2020-01-31")

            assert "Building optimal date ranges" in caplog.text
            assert "Generated 1 optimal date ranges" in caplog.text
            assert result == [("2020-01-01", "2020-01-31")]


if __name__ == "__main__":
    pytest.main([__file__])
