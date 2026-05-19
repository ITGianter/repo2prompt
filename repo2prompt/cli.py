"""CLI entry point for repo2prompt."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

import pyperclip
from dotenv import load_dotenv

from . import __version__
from .formatter import render, render_legacy
from .ignore import build_spec
from .log import get_logger, setup_logging
from .scanner import build_tree

logger = get_logger(__name__)


def _env_or(cli_value, env_key: str, default=None):
    """Return CLI value, then env var, then default."""
    return cli_value or os.environ.get(env_key) or default


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="repo2prompt",
        description="Convert a local project into LLM-ready prompt text with tree structure and embedded file contents.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Root directory of the project (default: current directory)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )
    parser.add_argument(
        "-e", "--exclude",
        action="append",
        default=[],
        help="Additional glob patterns to exclude (can be repeated)",
    )
    parser.add_argument(
        "-c", "--copy",
        action="store_true",
        help="Copy the generated output to the system clipboard",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Use legacy single-section format without LLM summaries (no API key needed)",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Launch interactive TUI to select files before generation",
    )

    # Verbosity control
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )
    verbosity_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Set explicit log level (overrides --verbose)",
    )

    llm_group = parser.add_argument_group("LLM Summary Options")
    llm_group.add_argument(
        "--model",
        help="LLM model name (env: R2P_MODEL, default: gpt-4o-mini)",
    )
    llm_group.add_argument(
        "--api-key",
        help="API key for LLM service (env: OPENAI_API_KEY)",
    )
    llm_group.add_argument(
        "--base-url",
        help="Custom API base URL for compatible services (env: OPENAI_BASE_URL)",
    )
    llm_group.add_argument(
        "--temperature",
        help="LLM temperature (env: R2P_TEMPERATURE, default: 0.3)",
    )
    llm_group.add_argument(
        "--max-workers",
        help="Concurrent LLM calls (env: R2P_MAX_WORKERS, default: 5)",
    )

    parser.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Maximum lines per file in output (head+tail preserved, middle omitted)",
    )

    outline_group = parser.add_argument_group("Outline Options")
    outline_group.add_argument(
        "--outline-only",
        action="store_true",
        help="Replace file content with code structure outline (class/function signatures)",
    )
    outline_group.add_argument(
        "--outline-threshold",
        type=int,
        default=None,
        metavar="SIZE",
        help="Only extract outlines for files larger than SIZE bytes",
    )

    token_group = parser.add_argument_group("Token Estimation")
    token_group.add_argument(
        "--show-tokens",
        action="store_true",
        help="Show token count and estimated cost after generation",
    )
    token_group.add_argument(
        "--token-model",
        default=None,
        help="Model for token counting (default: same as --model, or gpt-4o)",
    )

    args = parser.parse_args(argv)

    # Resolve log level
    if args.log_level:
        level = getattr(logging, args.log_level)
    elif args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    setup_logging(level)

    load_dotenv()

    t0 = time.monotonic()

    logger.info("repo2prompt v%s starting", __version__)

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        logger.error("'%s' is not a directory", args.path)
        sys.exit(1)

    logger.info("Root directory: %s", root)
    logger.info("Mode: %s", "legacy" if args.no_summary else "summary")
    logger.debug("Exclude patterns: %s", args.exclude or "(none)")

    spec = build_spec(root, extra_exclude=args.exclude or None)
    tree = build_tree(root, spec)

    if args.interactive:
        from .tui import launch_selector
        tree = launch_selector(tree, root)
        if tree is None:
            logger.info("Interactive selection cancelled.")
            sys.exit(0)

    if args.no_summary:
        output = render_legacy(
            tree, root, max_lines=args.max_lines,
            outline_only=args.outline_only, outline_threshold=args.outline_threshold,
        )
    else:
        api_key = _env_or(args.api_key, "OPENAI_API_KEY")
        if not api_key:
            logger.error("--api-key or OPENAI_API_KEY required for summary mode.")
            logger.error("Use --no-summary for the legacy format without LLM summaries.")
            sys.exit(1)

        from .summarizer import Summarizer, build_file_index
        model = _env_or(args.model, "R2P_MODEL", "gpt-4o-mini")
        base_url = _env_or(args.base_url, "OPENAI_BASE_URL")
        temperature = float(_env_or(args.temperature, "R2P_TEMPERATURE", "0.3"))
        max_workers = int(_env_or(args.max_workers, "R2P_MAX_WORKERS", "5"))

        logger.debug("LLM config: model=%s, base_url=%s, temperature=%s, max_workers=%s",
                      model, base_url, temperature, max_workers)

        summarizer = Summarizer(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
        )
        file_summaries = build_file_index(tree, root, summarizer, max_workers=max_workers)
        output = render(
            tree, file_summaries, max_lines=args.max_lines,
            outline_only=args.outline_only, outline_threshold=args.outline_threshold,
        )

    if args.show_tokens:
        from .token_utils import count_tokens, format_token_report
        token_model = args.token_model or (model if not args.no_summary else "gpt-4o")
        token_count = count_tokens(output, token_model)
        report = format_token_report(token_count, token_model, len(output))
        sys.stderr.write(report + "\n")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        logger.info("Output written to %s", args.output)
    else:
        sys.stdout.write(output)

    if args.copy:
        try:
            pyperclip.copy(output)
            logger.info("Output copied to clipboard (%d chars)", len(output))
        except Exception as e:
            logger.error("Failed to copy to clipboard: %s", e)

    elapsed = time.monotonic() - t0
    logger.info("Pipeline complete in %.2fs", elapsed)


if __name__ == "__main__":
    main()
