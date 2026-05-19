"""Tests for TUI file selector."""

from repo2prompt.scanner import Entry
from repo2prompt.tui import filter_tree


def _make_file(name: str, rel_path: str) -> Entry:
    return Entry(name=name, rel_path=rel_path, is_dir=False, children=[])


def _make_dir(name: str, rel_path: str, children: list[Entry]) -> Entry:
    return Entry(name=name, rel_path=rel_path, is_dir=True, children=children)


class TestFilterTree:
    def test_empty_selection(self):
        """No selection returns None."""
        tree = _make_dir("root", "", [_make_file("a.py", "a.py")])
        assert filter_tree(tree, set()) is None

    def test_single_file_selected(self):
        """Selecting a single file preserves it."""
        a = _make_file("a.py", "a.py")
        b = _make_file("b.py", "b.py")
        tree = _make_dir("root", "", [a, b])

        result = filter_tree(tree, {"a.py"})
        assert result is not None
        assert len(result.children) == 1
        assert result.children[0].name == "a.py"

    def test_all_files_selected(self):
        """Selecting all files preserves the full tree."""
        a = _make_file("a.py", "a.py")
        b = _make_file("b.py", "b.py")
        tree = _make_dir("root", "", [a, b])

        result = filter_tree(tree, {"a.py", "b.py"})
        assert result is not None
        assert len(result.children) == 2

    def test_nested_dir_partial_selection(self):
        """Selecting a file in a subdirectory preserves the directory structure."""
        inner = _make_file("c.py", "src/c.py")
        src_dir = _make_dir("src", "src", [inner])
        a = _make_file("a.py", "a.py")
        tree = _make_dir("root", "", [a, src_dir])

        result = filter_tree(tree, {"src/c.py"})
        assert result is not None
        # a.py not selected, so only src/ remains
        assert len(result.children) == 1
        assert result.children[0].name == "src"
        assert result.children[0].is_dir is True
        assert len(result.children[0].children) == 1
        assert result.children[0].children[0].name == "c.py"

    def test_empty_dir_pruned(self):
        """Directories with no selected children are pruned."""
        inner = _make_file("c.py", "src/c.py")
        src_dir = _make_dir("src", "src", [inner])
        a = _make_file("a.py", "a.py")
        tree = _make_dir("root", "", [a, src_dir])

        # Only select a.py, src/ should be pruned
        result = filter_tree(tree, {"a.py"})
        assert result is not None
        assert len(result.children) == 1
        assert result.children[0].name == "a.py"

    def test_deep_nesting(self):
        """Deeply nested structures are preserved correctly."""
        deep_file = _make_file("x.py", "a/b/c/x.py")
        c_dir = _make_dir("c", "a/b/c", [deep_file])
        b_dir = _make_dir("b", "a/b", [c_dir])
        a_dir = _make_dir("a", "a", [b_dir])
        tree = _make_dir("root", "", [a_dir])

        result = filter_tree(tree, {"a/b/c/x.py"})
        assert result is not None
        assert result.children[0].name == "a"
        assert result.children[0].children[0].name == "b"
        assert result.children[0].children[0].children[0].name == "c"
        assert result.children[0].children[0].children[0].children[0].name == "x.py"

    def test_selected_paths_not_in_tree(self):
        """Paths not in the tree are ignored."""
        a = _make_file("a.py", "a.py")
        tree = _make_dir("root", "", [a])

        result = filter_tree(tree, {"nonexistent.py"})
        assert result is None

    def test_mixed_selection(self):
        """Mix of files at different levels."""
        f1 = _make_file("a.py", "a.py")
        f2 = _make_file("b.py", "b/b.py")
        f3 = _make_file("c.py", "b/c.py")
        b_dir = _make_dir("b", "b", [f2, f3])
        tree = _make_dir("root", "", [f1, b_dir])

        result = filter_tree(tree, {"a.py", "b/c.py"})
        assert result is not None
        assert len(result.children) == 2
        # a.py at top level
        assert result.children[0].name == "a.py"
        # b/ directory with only c.py
        assert result.children[1].name == "b"
        assert len(result.children[1].children) == 1
        assert result.children[1].children[0].name == "c.py"

    def test_filter_preserves_entry_attributes(self):
        """Filtered entries retain their original attributes."""
        a = _make_file("a.py", "src/a.py")
        src_dir = _make_dir("src", "src", [a])
        tree = _make_dir("root", "", [src_dir])

        result = filter_tree(tree, {"src/a.py"})
        filtered_file = result.children[0].children[0]
        assert filtered_file.name == "a.py"
        assert filtered_file.rel_path == "src/a.py"
        assert filtered_file.is_dir is False
        assert filtered_file.children == []
