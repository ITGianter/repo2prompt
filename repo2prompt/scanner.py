"""Directory scanner: walk the tree, apply ignore rules, yield entries in sorted order."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterator

import pathspec

from .ignore import build_spec, is_ignored
from .log import get_logger

logger = get_logger(__name__)


@dataclass
class Entry:
    """A single node in the directory tree."""
    name: str
    rel_path: str        # POSIX-style relative path from root
    is_dir: bool
    children: list[Entry] = field(default_factory=list)


def _posix_join(*parts: str) -> str:
    return "/".join(parts)


def _collect_entries(root: str, rel_dir: str, spec: pathspec.PathSpec) -> list[Entry]:
    """List immediate children of *rel_dir*, filtering with *spec*, sorted dirs-first."""
    abs_dir = os.path.join(root, rel_dir) if rel_dir else root
    try:
        names = os.listdir(abs_dir)
    except PermissionError:
        logger.warning("Permission denied: %s", abs_dir)
        return []

    dirs: list[Entry] = []
    files: list[Entry] = []

    for name in sorted(names):
        rel = _posix_join(rel_dir, name) if rel_dir else name
        if is_ignored(rel, spec):
            continue
        abs_path = os.path.join(abs_dir, name)
        is_dir = os.path.isdir(abs_path)
        entry = Entry(name=name, rel_path=rel, is_dir=is_dir)
        if is_dir:
            dirs.append(entry)
        else:
            files.append(entry)

    logger.debug("Scanned %s: %d dirs, %d files", rel_dir or ".", len(dirs), len(files))
    return dirs + files


def build_tree(root: str, spec: pathspec.PathSpec) -> Entry:
    """Recursively build the full tree structure rooted at *root*."""
    logger.info("Scanning directory tree: %s", root)

    root_name = os.path.basename(os.path.abspath(root))
    root_entry = Entry(name=root_name, rel_path="", is_dir=True)
    _expand(root, root_entry, spec)

    dirs, files = _count_entries(root_entry)
    logger.info("Tree built: %d directories, %d files", dirs, files)
    return root_entry


def _expand(root: str, parent: Entry, spec: pathspec.PathSpec) -> None:
    abs_parent = os.path.join(root, parent.rel_path) if parent.rel_path else root
    for child in _collect_entries(root, parent.rel_path, spec):
        parent.children.append(child)
        if child.is_dir:
            _expand(root, child, spec)


def _count_entries(entry: Entry) -> tuple[int, int]:
    """Return (dir_count, file_count) for the tree."""
    dirs = 1 if entry.is_dir else 0
    files = 0 if entry.is_dir else 1
    for child in entry.children:
        d, f = _count_entries(child)
        dirs += d
        files += f
    return dirs, files
