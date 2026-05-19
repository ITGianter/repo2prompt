"""Unit tests for the formatter module."""

from __future__ import annotations

import os
import tempfile

from repo2prompt.formatter import render, render_legacy
from repo2prompt.ignore import build_spec
from repo2prompt.scanner import Entry, build_tree
from repo2prompt.summarizer import FileSummary, build_file_index


def _make_project(files: dict[str, str]) -> str:
    """Create a temp directory with the given files. Returns the root path."""
    root = tempfile.mkdtemp()
    for rel, content in files.items():
        abs_path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
    return root


def _build_summaries(root: str, tree: Entry) -> list[FileSummary]:
    """Build FileSummary list using the real file_reader (no LLM)."""
    from repo2prompt.file_reader import read_file

    summaries: list[FileSummary] = []
    counter = [0]

    def walk(entry: Entry):
        for child in entry.children:
            if child.is_dir:
                walk(child)
            else:
                counter[0] += 1
                abs_path = os.path.join(root, child.rel_path)
                rr = read_file(abs_path)
                summaries.append(FileSummary(
                    index=f"FILE_{counter[0]:03d}",
                    rel_path=child.rel_path,
                    summary=f"Summary of {child.name}",
                    content=rr.content,
                    language=rr.language,
                    warning=rr.warning,
                ))

    walk(tree)
    return summaries


# ---------------------------------------------------------------------------
# Legacy render tests (render_legacy)
# ---------------------------------------------------------------------------

def test_legacy_single_file():
    root = _make_project({"hello.py": 'print("hi")\n'})
    spec = build_spec(root)
    tree = build_tree(root, spec)
    output = render_legacy(tree, root)
    assert "hello.py" in output
    assert "<file_content>" in output
    assert "```python" in output
    assert 'print("hi")' in output
    assert "</file_content>" in output


def test_legacy_nested_dirs():
    root = _make_project({
        "src/main.py": "x = 1\n",
        "src/lib/util.py": "y = 2\n",
    })
    spec = build_spec(root)
    tree = build_tree(root, spec)
    output = render_legacy(tree, root)
    assert "src/" in output
    assert "lib/" in output
    assert "main.py" in output
    assert "util.py" in output


# ---------------------------------------------------------------------------
# New two-section render tests
# ---------------------------------------------------------------------------

def test_single_file():
    root = _make_project({"hello.py": 'print("hi")\n'})
    spec = build_spec(root)
    tree = build_tree(root, spec)
    summaries = _build_summaries(root, tree)
    output = render(tree, summaries)

    # Section 1: tree with summary and index
    assert "[FILE_001]" in output
    assert "hello.py" in output
    assert "Summary of hello.py" in output

    # Section 2: content index
    assert '```python' in output
    assert 'print("hi")' in output


def test_nested_dirs():
    root = _make_project({
        "src/main.py": "x = 1\n",
        "src/lib/util.py": "y = 2\n",
    })
    spec = build_spec(root)
    tree = build_tree(root, spec)
    summaries = _build_summaries(root, tree)
    output = render(tree, summaries)

    # Section 1: tree structure
    assert "src/" in output
    assert "lib/" in output
    assert "main.py" in output
    assert "util.py" in output

    # Section 2: content mapping
    assert "[FILE_001]" in output
    assert "[FILE_002]" in output


def test_prefix_alignment():
    """Tree prefix characters should be correct in Section 1."""
    root = _make_project({
        "a.txt": "line1\nline2\n",
        "b.txt": "only\n",
    })
    spec = build_spec(root)
    tree = build_tree(root, spec)
    summaries = _build_summaries(root, tree)
    output = render(tree, summaries)
    lines = output.splitlines()

    # Find the tree lines (Section 1, before the blank separator)
    tree_lines = []
    for line in lines:
        if line.strip() == "=" * 60:
            break
        tree_lines.append(line)

    # Check that connectors are present
    tree_text = "\n".join(tree_lines)
    assert "├──" in tree_text or "└──" in tree_text


def test_exclude_pattern():
    root = _make_project({
        "keep.py": "x = 1\n",
        "skip.log": "log data\n",
    })
    spec = build_spec(root)
    tree = build_tree(root, spec)
    summaries = _build_summaries(root, tree)
    output = render(tree, summaries)
    assert "keep.py" in output
    assert "skip.log" not in output


def test_two_section_format():
    """Output should have two sections separated by a blank line."""
    root = _make_project({"a.py": "x = 1\n"})
    spec = build_spec(root)
    tree = build_tree(root, spec)
    summaries = _build_summaries(root, tree)
    output = render(tree, summaries)

    assert "=" * 60 in output
    # Section 2 content block
    assert "[FILE_001] a.py" in output


def test_section2_content_mapping():
    """Index in Section 1 should match the same index in Section 2."""
    root = _make_project({
        "first.py": "a = 1\n",
        "second.py": "b = 2\n",
    })
    spec = build_spec(root)
    tree = build_tree(root, spec)
    summaries = _build_summaries(root, tree)
    output = render(tree, summaries)

    # Both indexes appear in both sections
    assert output.count("[FILE_001]") >= 2  # once in tree, once in content
    assert output.count("[FILE_002]") >= 2
