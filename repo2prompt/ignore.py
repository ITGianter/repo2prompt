"""Ignore rules: .gitignore parsing + hardcoded defaults for Python/Java/general."""

from __future__ import annotations

import os
from typing import Optional

import pathspec

from .log import get_logger

logger = get_logger(__name__)


# Hardcoded default ignore patterns (always applied, even without .gitignore)
_DEFAULT_PATTERNS: list[str] = [
    # Version control
    ".git/",
    # Node
    "node_modules/",
    # Python
    "__pycache__/",
    "venv/",
    ".env",
    "*.pyc",
    ".pytest_cache/",
    ".eggs/",
    "*.egg-info/",
    # Java
    "target/",
    "build/",
    "*.class",
    "*.jar",
    "*.war",
    ".gradle/",
    ".idea/",
    # Binary / media
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.bmp",
    "*.ico",
    "*.svg",
    "*.mp3",
    "*.mp4",
    "*.avi",
    "*.mov",
    "*.mkv",
    "*.wav",
    "*.flac",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.rar",
    "*.7z",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.bin",
    "*.dat",
    "*.db",
    "*.sqlite",
    "*.log",
    # Repo2prompt
    ".repo2prompt_cache.json",
]


def build_spec(
    root: str,
    extra_exclude: Optional[list[str]] = None,
) -> pathspec.PathSpec:
    """Build a combined PathSpec from .gitignore + defaults + user extras."""
    patterns: list[str] = list(_DEFAULT_PATTERNS)
    logger.info("Loaded %d default ignore patterns", len(_DEFAULT_PATTERNS))

    gitignore_path = os.path.join(root, ".gitignore")
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, encoding="utf-8", errors="replace") as f:
            gitignore_lines = f.read().splitlines()
            patterns.extend(gitignore_lines)
        logger.info("Loaded %d patterns from .gitignore", len(gitignore_lines))
    else:
        logger.debug("No .gitignore found at %s", gitignore_path)

    if extra_exclude:
        patterns.extend(extra_exclude)
        logger.info("Added %d user exclude patterns", len(extra_exclude))
        logger.debug("User exclude patterns: %s", extra_exclude)

    logger.debug("Total combined ignore patterns: %d", len(patterns))

    return pathspec.PathSpec.from_lines("gitignore", patterns)


def is_ignored(rel_path: str, spec: pathspec.PathSpec) -> bool:
    """Check whether *rel_path* (POSIX-style, relative to root) should be skipped."""
    if spec.match_file(rel_path):
        return True
    # Directory-only patterns (trailing slash) require the path to also
    # carry a trailing slash for pathspec to match.
    if not rel_path.endswith("/"):
        return spec.match_file(rel_path + "/")
    return False
