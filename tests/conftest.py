"""Shared fixtures for repo2prompt tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def make_project(tmp_path: Path):
    """Factory fixture: create a temp project from a {rel_path: content} dict.

    Usage:
        def test_something(make_project):
            root = make_project({"a.py": "print('hi')", "src/b.py": "x = 1"})
    """
    def _factory(files: dict[str, str]) -> Path:
        for rel, content in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return tmp_path
    return _factory
