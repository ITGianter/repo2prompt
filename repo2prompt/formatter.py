"""Tree + content fusion engine (DFS rendering with prefix alignment).

Supports two modes:
- render_legacy(): original single-section output with full content embedded in the tree.
- render(): two-section output -- tree with LLM summaries + separate content index.
"""

from __future__ import annotations

import os

from .extractor import extract_outline
from .file_reader import read_file, truncate_content
from .log import get_logger
from .scanner import Entry

logger = get_logger(__name__)

# Tree-drawing characters
_BRANCH_LAST = "└── "
_BRANCH_MID = "├── "
_CONT_SPACE = "    "
_CONT_PIPE = "│   "
_SECTION_SEP = "=" * 60


# ---------------------------------------------------------------------------
# Legacy single-section renderer (preserved for --no-summary mode)
# ---------------------------------------------------------------------------

def render_legacy(
    root_entry: Entry,
    root_path: str,
    max_lines: int | None = None,
    outline_only: bool = False,
    outline_threshold: int | None = None,
) -> str:
    """Render the full tree + embedded file content as a single string."""
    lines: list[str] = []
    _render_entry_legacy(
        root_entry, lines, prefix="", is_last=True, root_path=root_path,
        max_lines=max_lines, outline_only=outline_only, outline_threshold=outline_threshold,
    )
    output = "\n".join(lines) + "\n"
    logger.info("Legacy render complete: %d lines, %d bytes", len(lines), len(output))
    return output


def _render_entry_legacy(
    entry: Entry,
    lines: list[str],
    prefix: str,
    is_last: bool,
    root_path: str,
    max_lines: int | None = None,
    outline_only: bool = False,
    outline_threshold: int | None = None,
) -> None:
    connector = _BRANCH_LAST if is_last else _BRANCH_MID
    sub_prefix = prefix + (_CONT_SPACE if is_last else _CONT_PIPE)

    lines.append(prefix + connector + entry.name + ("/" if entry.is_dir else ""))

    if not entry.is_dir:
        abs_path = os.path.join(root_path, entry.rel_path)
        result = read_file(abs_path)
        _embed_content(
            lines, sub_prefix, result.content, result.language, result.warning,
            rel_path=entry.rel_path, max_lines=max_lines,
            outline_only=outline_only, outline_threshold=outline_threshold,
        )
        return

    for idx, child in enumerate(entry.children):
        child_is_last = idx == len(entry.children) - 1
        _render_entry_legacy(
            child, lines, sub_prefix, child_is_last, root_path,
            max_lines=max_lines, outline_only=outline_only, outline_threshold=outline_threshold,
        )


def _should_outline(content: str, language: str, outline_only: bool, outline_threshold: int | None) -> bool:
    """Determine if outline extraction should be applied."""
    if outline_only:
        return True
    if outline_threshold is not None and len(content.encode("utf-8")) > outline_threshold:
        return True
    return False


def _embed_content(
    lines: list[str],
    prefix: str,
    content: str | None,
    language: str,
    warning: str | None,
    rel_path: str = "",
    max_lines: int | None = None,
    outline_only: bool = False,
    outline_threshold: int | None = None,
) -> None:
    lines.append(prefix + "<file_content>")

    if warning:
        lines.append(prefix + f"<warning>{warning}</warning>")
    elif content is not None:
        display_content = content
        if _should_outline(content, language, outline_only, outline_threshold):
            display_content = extract_outline(content, language, rel_path)
        if max_lines is not None:
            display_content, _ = truncate_content(display_content, max_lines)
        lines.append(prefix + f"```{language}")
        for line in display_content.splitlines():
            lines.append(prefix + line)
        lines.append(prefix + "```")

    lines.append(prefix + "</file_content>")


# ---------------------------------------------------------------------------
# New two-section renderer
# ---------------------------------------------------------------------------

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .summarizer import FileSummary


def render(
    root_entry: Entry,
    file_summaries: list[FileSummary],
    max_lines: int | None = None,
    outline_only: bool = False,
    outline_threshold: int | None = None,
) -> str:
    """Render tree-with-summaries (Section 1) + content index (Section 2)."""
    summary_map = {fs.rel_path: fs for fs in file_summaries}

    section1 = _render_tree_with_summaries(root_entry, summary_map)
    section2 = _render_content_index(
        file_summaries, max_lines=max_lines,
        outline_only=outline_only, outline_threshold=outline_threshold,
    )

    output = section1 + "\n\n" + section2 + "\n"
    logger.info("Render complete: %d files summarized, output %d bytes",
                len(file_summaries), len(output))
    return output


def _render_tree_with_summaries(
    root_entry: Entry,
    summary_map: dict[str, FileSummary],
) -> str:
    lines: list[str] = []
    _render_tree_node(root_entry, lines, prefix="", is_last=True, summary_map=summary_map)
    return "\n".join(lines)


def _render_tree_node(
    entry: Entry,
    lines: list[str],
    prefix: str,
    is_last: bool,
    summary_map: dict[str, FileSummary],
) -> None:
    connector = _BRANCH_LAST if is_last else _BRANCH_MID
    sub_prefix = prefix + (_CONT_SPACE if is_last else _CONT_PIPE)

    if entry.is_dir:
        lines.append(prefix + connector + entry.name + "/")
        for idx, child in enumerate(entry.children):
            child_is_last = idx == len(entry.children) - 1
            _render_tree_node(child, lines, sub_prefix, child_is_last, summary_map)
    else:
        fs = summary_map.get(entry.rel_path)
        if fs:
            lines.append(f"{prefix}{connector}[{fs.index}] {entry.name} — {fs.summary}")
        else:
            lines.append(prefix + connector + entry.name)


def _render_content_index(
    file_summaries: list[FileSummary],
    max_lines: int | None = None,
    outline_only: bool = False,
    outline_threshold: int | None = None,
) -> str:
    blocks: list[str] = []
    for fs in file_summaries:
        block_lines: list[str] = []
        block_lines.append(_SECTION_SEP)
        block_lines.append(f"[{fs.index}] {fs.rel_path}")
        block_lines.append(_SECTION_SEP)

        if fs.warning:
            logger.debug("File %s has warning: %s", fs.rel_path, fs.warning)
            block_lines.append(f"<warning>{fs.warning}</warning>")
        elif fs.content is not None:
            display_content = fs.content
            if _should_outline(fs.content, fs.language, outline_only, outline_threshold):
                display_content = extract_outline(fs.content, fs.language, fs.rel_path)
            if max_lines is not None:
                display_content, _ = truncate_content(display_content, max_lines)
            block_lines.append(f"```{fs.language}")
            block_lines.append(display_content.rstrip())
            block_lines.append("```")

        blocks.append("\n".join(block_lines))

    return "\n\n".join(blocks)
