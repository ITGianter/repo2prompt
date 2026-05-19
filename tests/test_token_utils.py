"""Tests for token counting and cost estimation."""

from unittest.mock import MagicMock, patch

import pytest

from repo2prompt.token_utils import count_tokens, estimate_cost, format_token_report


class TestCountTokens:
    @patch("repo2prompt.token_utils.require_optional")
    def test_count_tokens_basic(self, mock_require):
        """Count tokens for a simple string."""
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
        with patch("tiktoken.encoding_for_model", return_value=mock_encoding):
            result = count_tokens("hello world", "gpt-4o")
        assert result == 5

    @patch("repo2prompt.token_utils.require_optional")
    def test_count_tokens_fallback(self, mock_require):
        """Fall back to cl100k_base for unknown models."""
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3]
        with patch("tiktoken.encoding_for_model", side_effect=KeyError("unknown")), \
             patch("tiktoken.get_encoding", return_value=mock_encoding):
            result = count_tokens("test", "unknown-model")
        assert result == 3

    def test_count_tokens_missing_tiktoken(self):
        """Clear error when tiktoken is not installed."""
        with patch("importlib.import_module", side_effect=ImportError("no tiktoken")):
            with pytest.raises(SystemExit):
                count_tokens("test")


class TestEstimateCost:
    def test_known_model(self):
        """Cost calculation for known model."""
        cost = estimate_cost(1_000_000, "gpt-4o")
        assert cost == 2.50

    def test_partial_tokens(self):
        """Cost scales linearly with token count."""
        cost = estimate_cost(500_000, "gpt-4o-mini")
        assert abs(cost - 0.075) < 1e-6

    def test_unknown_model(self):
        """Returns None for unknown model."""
        assert estimate_cost(1000, "unknown-model") is None


class TestFormatTokenReport:
    def test_known_model_report(self):
        """Report includes all fields for known model."""
        report = format_token_report(10000, "gpt-4o", 50000)
        assert "Characters: 50,000" in report
        assert "Tokens (gpt-4o): 10,000" in report
        assert "Estimated input cost:" in report
        assert "approximate" in report

    def test_unknown_model_report(self):
        """Report omits cost for unknown model."""
        report = format_token_report(10000, "custom-model", 50000)
        assert "Tokens (custom-model): 10,000" in report
        assert "Cost estimation unavailable" in report
        assert "Estimated input cost" not in report
