"""Unit tests for the scanner module."""

from __future__ import annotations

import os
from unittest.mock import patch

from repo2prompt.ignore import build_spec
from repo2prompt.scanner import Entry, _count_entries, build_tree


# ---------------------------------------------------------------------------
# build_tree — basic structure
# ---------------------------------------------------------------------------

class TestBuildTree:
    def test_single_file(self, make_project):
        root = make_project({"hello.py": 'print("hi")\n'})
        spec = build_spec(str(root))
        tree = build_tree(str(root), spec)

        assert tree.is_dir is True
        assert len(tree.children) == 1
        child = tree.children[0]
        assert child.name == "hello.py"
        assert child.is_dir is False

    def test_nested_dirs(self, make_project):
        root = make_project({
            "src/main.py": "x = 1\n",
            "src/lib/util.py": "y = 2\n",
        })
        spec = build_spec(str(root))
        tree = build_tree(str(root), spec)

        # root -> src/ -> [lib/, main.py]
        src = tree.children[0]
        assert src.name == "src"
        assert src.is_dir is True

        lib = src.children[0]
        assert lib.name == "lib"
        assert lib.is_dir is True

        assert lib.children[0].name == "util.py"
        assert src.children[1].name == "main.py"

    def test_root_name_matches_dir(self, make_project):
        root = make_project({"a.py": ""})
        spec = build_spec(str(root))
        tree = build_tree(str(root), spec)
        # root name should be the directory basename
        assert tree.name == root.name


# ---------------------------------------------------------------------------
# Sorting: dirs before files, alphabetical within group
# ---------------------------------------------------------------------------

class TestSorting:
    def test_dirs_before_files(self, make_project):
        root = make_project({
            "sub/nested.py": "",
            "a_file.py": "",
            "z_file.py": "",
            "another_dir/x.py": "",
        })
        spec = build_spec(str(root))
        tree = build_tree(str(root), spec)

        names = [c.name for c in tree.children]
        dir_names = [c.name for c in tree.children if c.is_dir]
        file_names = [c.name for c in tree.children if not c.is_dir]

        # All dirs should come before all files
        first_file_idx = next(i for i, c in enumerate(tree.children) if not c.is_dir)
        last_dir_idx = len(dir_names) - 1
        assert last_dir_idx < first_file_idx

    def test_alphabetical_sort(self, make_project):
        root = make_project({
            "z.py": "",
            "a.py": "",
            "m.py": "",
        })
        spec = build_spec(str(root))
        tree = build_tree(str(root), spec)

        names = [c.name for c in tree.children]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# Ignore integration
# ---------------------------------------------------------------------------

class TestIgnoreIntegration:
    def test_ignored_files_excluded(self, make_project):
        root = make_project({
            "keep.py": "x = 1\n",
            "skip.log": "log data\n",
        })
        spec = build_spec(str(root))
        tree = build_tree(str(root), spec)

        names = [c.name for c in tree.children]
        assert "keep.py" in names
        assert "skip.log" not in names

    def test_ignored_dirs_excluded(self, make_project):
        """Directories matching ignore patterns (with trailing slash) should
        not appear in the tree at all."""
        root = make_project({
            "src/app.py": "x = 1\n",
            "__pycache__/cache.pyc": "binary",
            "node_modules/pkg/index.js": "y = 2\n",
        })
        spec = build_spec(str(root))
        tree = build_tree(str(root), spec)

        names = [c.name for c in tree.children]
        assert "src" in names
        assert "__pycache__" not in names
        assert "node_modules" not in names


# ---------------------------------------------------------------------------
# Empty directory
# ---------------------------------------------------------------------------

class TestEmptyDir:
    def test_empty_subdir(self, make_project):
        root = make_project({})
        # Create an empty directory manually
        os.makedirs(str(root / "empty_dir"), exist_ok=True)
        spec = build_spec(str(root))
        tree = build_tree(str(root), spec)

        empty = tree.children[0]
        assert empty.name == "empty_dir"
        assert empty.is_dir is True
        assert empty.children == []


# ---------------------------------------------------------------------------
# Permission denied
# ---------------------------------------------------------------------------

class TestPermissionDenied:
    def test_permission_denied_returns_empty_children(self, make_project):
        root = make_project({"a.py": ""})
        spec = build_spec(str(root))

        original_listdir = os.listdir

        def mock_listdir(path):
            if "restricted" in str(path):
                raise PermissionError("access denied")
            return original_listdir(path)

        # Create a restricted dir manually
        os.makedirs(str(root / "restricted"), exist_ok=True)

        with patch("repo2prompt.scanner.os.listdir", side_effect=mock_listdir):
            tree = build_tree(str(root), spec)

        names = [c.name for c in tree.children]
        assert "restricted" in names
        restricted = next(c for c in tree.children if c.name == "restricted")
        assert restricted.children == []


# ---------------------------------------------------------------------------
# _count_entries
# ---------------------------------------------------------------------------

class TestCountEntries:
    def test_single_file(self):
        root = Entry(name="root", rel_path="", is_dir=True, children=[
            Entry(name="a.py", rel_path="a.py", is_dir=False),
        ])
        dirs, files = _count_entries(root)
        assert dirs == 1  # root
        assert files == 1

    def test_nested(self):
        sub = Entry(name="sub", rel_path="sub", is_dir=True, children=[
            Entry(name="b.py", rel_path="sub/b.py", is_dir=False),
        ])
        root = Entry(name="root", rel_path="", is_dir=True, children=[
            sub,
            Entry(name="a.py", rel_path="a.py", is_dir=False),
        ])
        dirs, files = _count_entries(root)
        assert dirs == 2  # root + sub
        assert files == 2  # a.py + b.py
