"""Safe file reading: encoding fallback, size limit, language detection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .log import get_logger

logger = get_logger(__name__)

# Max bytes to read per file (512 KB)
MAX_FILE_SIZE = 512 * 1024

# Whitelisted extensions -> markdown code-block language
_EXT_LANG: dict[str, str] = {
    # Python
    ".py": "python",
    ".pyi": "python",
    ".ipynb": "json",
    # Java
    ".java": "java",
    # JVM build
    ".xml": "xml",
    ".gradle": "groovy",
    ".properties": "properties",
    # Web / config
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "text",
    # Markup / docs
    ".md": "markdown",
    ".txt": "text",
    ".csv": "text",
    ".rst": "text",
    # Shell
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    # Other
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".js": "javascript",
    ".ts": "typescript",
}

# Basenames that should be captured regardless of extension
_WHITELIST_BASENAMES: set[str] = {
    "requirements.txt",
    "Pipfile",
    "Pipfile.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Dockerfile",
    "Makefile",
    ".gitignore",
    ".dockerignore",
}


@dataclass
class ReadResult:
    """Outcome of attempting to read a file."""
    content: Optional[str]   # None when unreadable / too large
    language: str            # markdown language tag ("" if unknown)
    warning: Optional[str]   # e.g. "File too large to display"


def _detect_language(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    lang = _EXT_LANG.get(ext, "")
    if not lang:
        basename = os.path.basename(filepath)
        if basename in _WHITELIST_BASENAMES:
            lang = "text"
    return lang


def _is_whitelisted(filepath: str) -> bool:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in _EXT_LANG:
        return True
    basename = os.path.basename(filepath)
    return basename in _WHITELIST_BASENAMES


def read_file(filepath: str) -> ReadResult:
    """Safely read a file, respecting size limits and encoding fallbacks."""
    lang = _detect_language(filepath)
    if not lang:
        logger.debug("Skipping non-whitelisted file: %s", filepath)
        return ReadResult(content=None, language="", warning=None)

    try:
        size = os.path.getsize(filepath)
    except OSError:
        logger.warning("Cannot access file: %s", filepath)
        return ReadResult(content=None, language=lang, warning="Cannot access file")

    if size > MAX_FILE_SIZE:
        logger.debug("File too large (%d bytes > %d): %s", size, MAX_FILE_SIZE, filepath)
        return ReadResult(content=None, language=lang, warning="File too large to display")

    for encoding in ("utf-8", "latin-1"):
        try:
            with open(filepath, encoding=encoding) as f:
                text = f.read()
            if encoding != "utf-8":
                logger.debug("Encoding fallback: %s used %s (utf-8 failed)", filepath, encoding)
            logger.debug("Read %s (%d bytes, encoding=%s, lang=%s)", filepath, len(text), encoding, lang)
            return ReadResult(content=text, language=lang, warning=None)
        except (UnicodeDecodeError, UnicodeError):
            logger.debug("Decode failed for %s with %s", filepath, encoding)
            continue
        except OSError:
            logger.warning("Cannot read file: %s", filepath)
            return ReadResult(content=None, language=lang, warning="Cannot read file")

    logger.warning("Unable to decode file: %s", filepath)
    return ReadResult(content=None, language=lang, warning="Unable to decode file")


def truncate_content(content: str, max_lines: int, head_ratio: float = 0.7) -> tuple[str, bool]:
    """Truncate content to max_lines, keeping head and tail.

    Returns (truncated_text, was_truncated).
    """
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content, False

    head_count = int(max_lines * head_ratio)
    tail_count = max_lines - head_count
    omitted = len(lines) - head_count - tail_count

    head = lines[:head_count]
    tail = lines[-tail_count:] if tail_count > 0 else []
    marker = f"... [Omitting {omitted} lines for brevity] ..."

    return "\n".join(head + ["", marker, ""] + tail), True
