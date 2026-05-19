"""Web-aware pipeline runner for repo2prompt.

This module provides an async wrapper around the core pipeline functions,
emitting structured events for real-time progress reporting via SSE.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

from ..formatter import render, render_legacy
from ..ignore import build_spec
from ..scanner import build_tree
from ..summarizer import Summarizer, build_file_index

logger = logging.getLogger(__name__)


@dataclass
class RunParams:
    """Parameters for a pipeline run, mirroring CLI arguments."""
    path: str = "."
    output: str | None = None
    exclude: list[str] = field(default_factory=list)
    copy: bool = False
    no_summary: bool = False
    interactive: bool = False
    verbose: int = 0
    log_level: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.3
    max_workers: int = 5
    max_lines: int | None = None
    outline_only: bool = False
    outline_threshold: int | None = None
    show_tokens: bool = False
    token_model: str | None = None


class PipelineError(Exception):
    """Raised when the pipeline encounters a recoverable error."""

    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


async def run_pipeline(
    params: RunParams,
    event_queue: asyncio.Queue[dict[str, Any]],
    cancel_event: asyncio.Event,
) -> None:
    """Execute the repo2prompt pipeline, emitting events to *event_queue*.

    The pipeline is run in a background thread to avoid blocking the event loop.
    """
    load_dotenv()
    t0 = time.monotonic()

    try:
        # --- Validation ---
        if params.interactive:
            raise PipelineError(
                "Interactive mode (TUI) is not available in the web interface.",
                "INTERACTIVE_NOT_SUPPORTED",
            )

        root = os.path.abspath(params.path)
        if not os.path.isdir(root):
            raise PipelineError(
                f"'{params.path}' is not a valid directory.",
                "INVALID_PATH",
            )

        await _emit(event_queue, {
            "type": "log",
            "level": "info",
            "msg": f"Scanning directory: {root}",
        })

        if cancel_event.is_set():
            raise PipelineError("Run cancelled by user.", "CANCELLED")

        # --- Build tree ---
        spec = await asyncio.to_thread(build_spec, root, params.exclude or None)
        tree = await asyncio.to_thread(build_tree, root, spec)

        file_count = sum(1 for e in _walk(tree) if not e.is_dir)
        await _emit(event_queue, {
            "type": "log",
            "level": "info",
            "msg": f"Found {file_count} files",
        })

        if cancel_event.is_set():
            raise PipelineError("Run cancelled by user.", "CANCELLED")

        # --- Render ---
        if params.no_summary:
            output = await asyncio.to_thread(
                render_legacy,
                tree, root,
                max_lines=params.max_lines,
                outline_only=params.outline_only,
                outline_threshold=params.outline_threshold,
            )
        else:
            # Summary mode requires API key
            api_key = params.api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise PipelineError(
                    "API key is required for summary mode. "
                    "Set --api-key or the OPENAI_API_KEY environment variable.",
                    "MISSING_API_KEY",
                )

            model = params.model or os.environ.get("R2P_MODEL", "gpt-4o-mini")
            base_url = params.base_url or os.environ.get("OPENAI_BASE_URL")
            temperature = params.temperature
            max_workers = params.max_workers

            summarizer = Summarizer(
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
            )

            # Progress callback for SSE
            # Capture the event loop before entering the thread
            loop = asyncio.get_event_loop()

            def on_progress(completed: int, total: int, file_path: str) -> None:
                asyncio.run_coroutine_threadsafe(
                    _emit(event_queue, {
                        "type": "progress",
                        "current": completed,
                        "total": total,
                        "file": file_path,
                    }),
                    loop,
                )

            await _emit(event_queue, {
                "type": "log",
                "level": "info",
                "msg": f"Summarizing files with {model} ({max_workers} workers)...",
            })

            file_summaries = await asyncio.to_thread(
                build_file_index,
                tree, root, summarizer, max_workers,
                on_progress,
            )

            if cancel_event.is_set():
                raise PipelineError("Run cancelled by user.", "CANCELLED")

            output = await asyncio.to_thread(
                render,
                tree, file_summaries,
                max_lines=params.max_lines,
                outline_only=params.outline_only,
                outline_threshold=params.outline_threshold,
            )

        # --- Token estimation (optional) ---
        if params.show_tokens:
            try:
                from ..token_utils import count_tokens, format_token_report
                token_model = params.token_model or (
                    model if not params.no_summary else "gpt-4o"
                )
                token_count = await asyncio.to_thread(count_tokens, output, token_model)
                report = format_token_report(token_count, token_model, len(output))
                await _emit(event_queue, {
                    "type": "log",
                    "level": "info",
                    "msg": report,
                })
            except Exception as e:
                await _emit(event_queue, {
                    "type": "log",
                    "level": "warning",
                    "msg": f"Token estimation failed: {e}",
                })

        # --- Emit output ---
        await _emit(event_queue, {
            "type": "output",
            "content": output,
        })

        # --- Done ---
        elapsed = time.monotonic() - t0
        await _emit(event_queue, {
            "type": "done",
            "elapsed": round(elapsed, 2),
            "bytes": len(output),
        })

    except PipelineError as e:
        await _emit(event_queue, {
            "type": "error",
            "msg": e.message,
            "code": e.code,
        })
    except Exception as e:
        logger.exception("Pipeline failed with unexpected error")
        await _emit(event_queue, {
            "type": "error",
            "msg": f"Internal error: {e}",
            "code": "INTERNAL_ERROR",
        })


async def _emit(queue: asyncio.Queue[dict[str, Any]], event: dict[str, Any]) -> None:
    """Put an event into the queue."""
    await queue.put(event)


def _walk(entry):
    """Yield all entries in DFS order."""
    yield entry
    for child in entry.children:
        yield from _walk(child)
