"""Tests for optional dependency checker."""

from unittest.mock import patch

import pytest

from repo2prompt._optional import require_optional


def test_require_optional_installed():
    """No error when the package exists."""
    require_optional("os", "Test feature")  # 'os' is always available


def test_require_optional_missing():
    """SystemExit with helpful message when package is missing."""
    with patch("importlib.import_module", side_effect=ImportError("no module")):
        with pytest.raises(SystemExit) as exc_info:
            require_optional("tiktoken", "Token estimation")
        assert exc_info.value.code == 1


def test_require_optional_missing_message(capsys):
    """Error message includes package name and feature name."""
    with patch("importlib.import_module", side_effect=ImportError("no module")):
        with pytest.raises(SystemExit):
            require_optional("textual", "Interactive mode")
    captured = capsys.readouterr()
    assert "textual" in captured.err
    assert "Interactive mode" in captured.err
    assert "pip install textual" in captured.err
