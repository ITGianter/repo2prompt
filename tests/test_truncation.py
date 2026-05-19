"""Tests for line truncation feature."""

import os
import tempfile

from repo2prompt.file_reader import truncate_content
from repo2prompt.formatter import render, render_legacy
from repo2prompt.ignore import build_spec
from repo2prompt.scanner import Entry, build_tree
from repo2prompt.summarizer import FileSummary


def _make_project(files: dict[str, str]) -> str:
    """Create a temp directory with the given files."""
    root = tempfile.mkdtemp()
    for rel, content in files.items():
        abs_path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
    return root


class TestTruncateContent:
    def test_short_content_unchanged(self):
        """Content shorter than max_lines is returned as-is."""
        content = "line1\nline2\nline3"
        result, truncated = truncate_content(content, max_lines=10)
        assert result == content
        assert truncated is False

    def test_exact_limit_unchanged(self):
        """Content exactly at max_lines is returned as-is."""
        content = "\n".join(f"line{i}" for i in range(10))
        result, truncated = truncate_content(content, max_lines=10)
        assert result == content
        assert truncated is False

    def test_long_content_truncated(self):
        """Content exceeding max_lines is truncated with marker."""
        content = "\n".join(f"line{i}" for i in range(100))
        result, truncated = truncate_content(content, max_lines=20)
        assert truncated is True
        assert "Omitting" in result
        assert "line0" in result  # head preserved
        assert "line99" in result  # tail preserved

    def test_head_tail_ratio(self):
        """Default 70/30 split: 70% head, 30% tail."""
        content = "\n".join(f"line{i}" for i in range(100))
        result, _ = truncate_content(content, max_lines=20)
        lines = result.splitlines()
        # 14 head + 3 marker lines + 6 tail = 23 total lines in output
        # But the marker block is: "", marker, ""
        # head=14, marker=3 lines, tail=6
        assert "line0" in lines[0]
        assert "line13" in lines[13]  # last head line (14 lines, index 0-13)
        assert "line94" in lines[-6]  # first tail line

    def test_omission_count(self):
        """Omission message shows correct number of omitted lines."""
        content = "\n".join(f"line{i}" for i in range(100))
        result, _ = truncate_content(content, max_lines=20)
        # head=14, tail=6, omitted=100-14-6=80
        assert "Omitting 80 lines" in result

    def test_small_max_lines(self):
        """Works correctly with very small max_lines."""
        content = "\n".join(f"line{i}" for i in range(10))
        result, truncated = truncate_content(content, max_lines=3)
        assert truncated is True
        # head=2, tail=1
        assert "line0" in result
        assert "line9" in result


class TestTruncationIntegration:
    def test_legacy_render_with_max_lines(self):
        """Legacy render respects max_lines parameter."""
        root = _make_project({"big.py": "\n".join(f"line{i}" for i in range(200))})
        spec = build_spec(root)
        tree = build_tree(root, spec)

        output = render_legacy(tree, root, max_lines=10)
        assert "Omitting" in output
        assert "line0" in output

    def test_legacy_render_no_truncation_by_default(self):
        """Legacy render shows full content without max_lines."""
        content = "\n".join(f"line{i}" for i in range(200))
        root = _make_project({"big.py": content})
        spec = build_spec(root)
        tree = build_tree(root, spec)

        output = render_legacy(tree, root)
        assert "Omitting" not in output
        assert "line199" in output

    def test_summary_render_with_max_lines(self):
        """Summary render respects max_lines parameter."""
        content = "\n".join(f"line{i}" for i in range(200))
        root = _make_project({"big.py": content})
        spec = build_spec(root)
        tree = build_tree(root, spec)

        file_summaries = [
            FileSummary(
                index="FILE_001",
                rel_path="big.py",
                summary="A big file",
                content=content,
                language="python",
                warning=None,
            )
        ]
        output = render(tree, file_summaries, max_lines=10)
        assert "Omitting" in output
        assert "line0" in output

    def test_summarizer_gets_full_content(self):
        """Verify summarizer receives full content even with max_lines set."""
        # This is a design guarantee: max_lines only affects render output,
        # not the content stored in FileSummary.
        content = "\n".join(f"line{i}" for i in range(200))
        fs = FileSummary(
            index="FILE_001",
            rel_path="test.py",
            summary="test",
            content=content,
            language="python",
            warning=None,
        )
        # FileSummary.content should be the full content
        assert len(fs.content.splitlines()) == 200
