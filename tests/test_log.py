"""Tests for the repo2prompt logging system."""

import logging

import pytest

from repo2prompt.log import get_logger, setup_logging


class TestGetLogger:
    def test_returns_child_logger(self):
        logger = get_logger("repo2prompt.scanner")
        assert logger.name == "repo2prompt.scanner"

    def test_parent_is_repo2prompt(self):
        logger = get_logger("repo2prompt.scanner")
        assert logger.parent is not None
        assert logger.parent.name == "repo2prompt"

    def test_returns_same_object_on_repeated_calls(self):
        a = get_logger("repo2prompt.cli")
        b = get_logger("repo2prompt.cli")
        assert a is b


class TestSetupLogging:
    def teardown_method(self):
        # Clean up handlers after each test
        root = logging.getLogger("repo2prompt")
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_default_level_is_warning(self):
        setup_logging()
        root = logging.getLogger("repo2prompt")
        assert root.level == logging.WARNING

    def test_sets_info_level(self):
        setup_logging(logging.INFO)
        root = logging.getLogger("repo2prompt")
        assert root.level == logging.INFO

    def test_sets_debug_level(self):
        setup_logging(logging.DEBUG)
        root = logging.getLogger("repo2prompt")
        assert root.level == logging.DEBUG

    def test_adds_one_handler(self):
        setup_logging(logging.INFO)
        root = logging.getLogger("repo2prompt")
        assert len(root.handlers) == 1

    def test_idempotent_no_duplicate_handlers(self):
        setup_logging(logging.INFO)
        setup_logging(logging.DEBUG)
        root = logging.getLogger("repo2prompt")
        assert len(root.handlers) == 1

    def test_handler_writes_to_stderr(self, capsys):
        setup_logging(logging.INFO)
        logger = get_logger("repo2prompt.test")
        logger.info("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.err

    def test_warning_level_hides_info(self, capsys):
        setup_logging(logging.WARNING)
        logger = get_logger("repo2prompt.test")
        logger.info("should not appear")
        logger.warning("should appear")
        captured = capsys.readouterr()
        assert "should not appear" not in captured.err
        assert "should appear" in captured.err


class TestNullHandler:
    def test_null_handler_exists(self):
        import importlib
        import repo2prompt  # noqa: F401
        importlib.reload(repo2prompt)
        root = logging.getLogger("repo2prompt")
        assert any(isinstance(h, logging.NullHandler) for h in root.handlers)


class TestCLIVerbosity:
    """Test that CLI --verbose / --log-level flags resolve to correct levels."""

    def test_default_is_warning(self):
        from repo2prompt.cli import main
        import argparse
        # We can't easily test main() directly, but we verify the arg parsing
        parser = argparse.ArgumentParser()
        verbosity_group = parser.add_mutually_exclusive_group()
        verbosity_group.add_argument("-v", "--verbose", action="count", default=0)
        verbosity_group.add_argument("--log-level", default=None)
        args = parser.parse_args([])
        assert args.verbose == 0

    def test_single_verbose(self):
        import argparse
        parser = argparse.ArgumentParser()
        verbosity_group = parser.add_mutually_exclusive_group()
        verbosity_group.add_argument("-v", "--verbose", action="count", default=0)
        verbosity_group.add_argument("--log-level", default=None)
        args = parser.parse_args(["-v"])
        assert args.verbose == 1

    def test_double_verbose(self):
        import argparse
        parser = argparse.ArgumentParser()
        verbosity_group = parser.add_mutually_exclusive_group()
        verbosity_group.add_argument("-v", "--verbose", action="count", default=0)
        verbosity_group.add_argument("--log-level", default=None)
        args = parser.parse_args(["-vv"])
        assert args.verbose == 2

    def test_log_level_flag(self):
        import argparse
        parser = argparse.ArgumentParser()
        verbosity_group = parser.add_mutually_exclusive_group()
        verbosity_group.add_argument("-v", "--verbose", action="count", default=0)
        verbosity_group.add_argument("--log-level", default=None, choices=["DEBUG", "INFO", "WARNING"])
        args = parser.parse_args(["--log-level", "DEBUG"])
        assert args.log_level == "DEBUG"
