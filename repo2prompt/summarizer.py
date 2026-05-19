"""LLM-powered file summarization via langchain_openai."""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import openai
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .file_reader import read_file
from .log import get_logger
from .scanner import Entry

logger = get_logger(__name__)


@dataclass
class FileSummary:
    """Summary and metadata for a single file."""
    index: str           # e.g. "FILE_001"
    rel_path: str        # POSIX relative path
    summary: str         # LLM-generated summary
    content: Optional[str]  # full file content
    language: str        # code-block language tag
    warning: Optional[str]  # read error/warning


class Summarizer:
    """Wraps OpenAI API to produce one-line file summaries."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        temperature: float = 0.3,
    ) -> None:
        self.model = model
        self.temperature = temperature
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        # Explicitly create httpx client without proxy settings to avoid compatibility issues
        import httpx
        kwargs["http_client"] = httpx.Client(proxy=None)
        self._client = openai.OpenAI(**kwargs)
        logger.debug("Summarizer initialized: model=%s, base_url=%s, temperature=%s",
                      model, base_url, temperature)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _call_llm(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        if resp.choices and resp.choices[0].message.content:
            return resp.choices[0].message.content.strip()
        return "[Empty summary]"

    def summarize(self, content: str, file_path: str) -> str:
        """Return a one-sentence summary of *content*, or a fallback on failure."""
        prompt = (
            f"Summarize the purpose of this file in one concise sentence. "
            f"Do not include code snippets. File path: {file_path}\n\n"
            f"File content:\n{content}"
        )
        try:
            return self._call_llm(prompt)
        except Exception as exc:
            logger.warning("Summarization failed for %s: %s", file_path, exc)
            return "[Summary generation failed]"


def build_file_index(
    root_entry: Entry,
    root_path: str,
    summarizer: Summarizer,
    max_workers: int = 5,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[FileSummary]:
    """Walk the Entry tree, read files, generate summaries, and return an ordered list.

    Args:
        progress_callback: Optional callback ``(completed, total, file_path)``
            invoked after each file is summarized. When provided, the Rich
            progress bar is disabled so that the caller can report progress
            itself (e.g. via SSE in the web interface).
    """
    # Collect all file entries in DFS order
    file_entries: list[Entry] = []
    _collect_files(root_entry, file_entries)
    total = len(file_entries)
    logger.info("Building file index for %d files", total)

    # Load Cache
    cache_path = os.path.join(root_path, ".repo2prompt_cache.json")
    cache: dict[str, dict[str, str]] = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception as e:
            logger.warning("Failed to load cache %s: %s", cache_path, e)

    # Read all files and prepare tasks
    results: list[FileSummary] = [None] * total  # type: ignore[list-item]
    summarize_tasks: list[tuple[int, str, str, str]] = []  # (index, content, rel_path, hash)

    for i, entry in enumerate(file_entries):
        abs_path = os.path.join(root_path, entry.rel_path)
        rr = read_file(abs_path)
        idx_str = f"FILE_{i + 1:03d}"

        if rr.warning or rr.content is None:
            summary = rr.warning or "File not readable"
            results[i] = FileSummary(
                index=idx_str,
                rel_path=entry.rel_path,
                summary=summary,
                content=rr.content,
                language=rr.language,
                warning=rr.warning,
            )
            logger.debug("Skipping summarization for %s: %s",
                         entry.rel_path, rr.warning or "no content")
        else:
            content_hash = hashlib.sha256((entry.rel_path + "\n" + rr.content).encode("utf-8")).hexdigest()
            cached_entry = cache.get(entry.rel_path)
            
            if cached_entry and cached_entry.get("hash") == content_hash:
                results[i] = FileSummary(
                    index=idx_str,
                    rel_path=entry.rel_path,
                    summary=cached_entry.get("summary", ""),
                    content=rr.content,
                    language=rr.language,
                    warning=None,
                )
                logger.debug("Cache hit for %s", entry.rel_path)
            else:
                results[i] = FileSummary(
                    index=idx_str,
                    rel_path=entry.rel_path,
                    summary="",
                    content=rr.content,
                    language=rr.language,
                    warning=None,
                )
                summarize_tasks.append((i, rr.content, entry.rel_path, content_hash))

    # Summarize in parallel
    if summarize_tasks:
        logger.info("Summarizing %d files with %d workers", len(summarize_tasks), max_workers)

        if progress_callback is None:
            # Original Rich progress bar path (CLI usage)
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("({task.completed}/{task.total})"),
                transient=True,
            )

            with progress:
                task_id = progress.add_task("Summarizing files...", total=len(summarize_tasks))
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    future_map = {
                        pool.submit(summarizer.summarize, content, rel_path): (i, rel_path, content_hash)
                        for i, content, rel_path, content_hash in summarize_tasks
                    }
                    for future in as_completed(future_map):
                        i, rel_path, content_hash = future_map[future]
                        summary = future.result()
                        results[i].summary = summary
                        if not summary.startswith("[Summary generation failed]"):
                            cache[rel_path] = {"hash": content_hash, "summary": summary}
                        progress.advance(task_id)
                        logger.debug("Summarized %s", rel_path)
        else:
            # Web mode: report progress via callback
            completed = 0
            total_tasks = len(summarize_tasks)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {
                    pool.submit(summarizer.summarize, content, rel_path): (i, rel_path, content_hash)
                    for i, content, rel_path, content_hash in summarize_tasks
                }
                for future in as_completed(future_map):
                    i, rel_path, content_hash = future_map[future]
                    summary = future.result()
                    results[i].summary = summary
                    if not summary.startswith("[Summary generation failed]"):
                        cache[rel_path] = {"hash": content_hash, "summary": summary}
                    completed += 1
                    progress_callback(completed, total_tasks, rel_path)
                    logger.debug("Summarized %s", rel_path)

        # Save Cache
        if summarize_tasks:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("Failed to save cache %s: %s", cache_path, e)

    logger.info("File index complete: %d files, %d summarized, %d skipped/failed",
                total, len(summarize_tasks), total - len(summarize_tasks))
    return results


def _collect_files(entry: Entry, out: list[Entry]) -> None:
    """DFS-collect all file entries."""
    for child in entry.children:
        if child.is_dir:
            _collect_files(child, out)
        else:
            out.append(child)
