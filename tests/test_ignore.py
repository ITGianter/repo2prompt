"""Unit tests for the ignore module."""

from __future__ import annotations

from repo2prompt.ignore import build_spec, is_ignored


# ---------------------------------------------------------------------------
# Default patterns — common directories
# ---------------------------------------------------------------------------

class TestDefaultPatterns:
    def test_git_dir(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored(".git/config", spec) is True

    def test_pycache(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("__pycache__/cache.pyc", spec) is True

    def test_node_modules(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("node_modules/pkg/index.js", spec) is True

    def test_venv(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("venv/lib/python3.py", spec) is True

    def test_env_file(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored(".env", spec) is True

    def test_java_target(self, make_project):
        root = make_project({"src/App.java": ""})
        spec = build_spec(str(root))
        assert is_ignored("target/classes/App.class", spec) is True

    def test_java_build(self, make_project):
        root = make_project({"src/App.java": ""})
        spec = build_spec(str(root))
        assert is_ignored("build/libs/app.jar", spec) is True

    def test_gradle(self, make_project):
        root = make_project({"src/App.java": ""})
        spec = build_spec(str(root))
        assert is_ignored(".gradle/cache", spec) is True

    def test_idea(self, make_project):
        root = make_project({"src/App.java": ""})
        spec = build_spec(str(root))
        assert is_ignored(".idea/workspace.xml", spec) is True


# ---------------------------------------------------------------------------
# Default patterns — binary / media files
# ---------------------------------------------------------------------------

class TestDefaultBinaryPatterns:
    def test_png(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("images/logo.png", spec) is True

    def test_exe(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("bin/app.exe", spec) is True

    def test_zip(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("dist/release.zip", spec) is True

    def test_pdf(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("docs/manual.pdf", spec) is True

    def test_log(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("app.log", spec) is True


# ---------------------------------------------------------------------------
# Default patterns — repo2prompt cache
# ---------------------------------------------------------------------------

class TestCachePattern:
    def test_cache_file_ignored(self, make_project):
        root = make_project({"src/app.py": ""})
        spec = build_spec(str(root))
        assert is_ignored(".repo2prompt_cache.json", spec) is True


# ---------------------------------------------------------------------------
# .gitignore merging
# ---------------------------------------------------------------------------

class TestGitignoreMerging:
    def test_gitignore_rules_merged(self, make_project):
        root = make_project({
            ".gitignore": "*.tmp\nsecret/\n",
            "app.py": "x = 1\n",
        })
        spec = build_spec(str(root))
        assert is_ignored("build.tmp", spec) is True
        assert is_ignored("secret/key.pem", spec) is True

    def test_defaults_still_apply_with_gitignore(self, make_project):
        root = make_project({
            ".gitignore": "*.tmp\n",
            "app.py": "x = 1\n",
        })
        spec = build_spec(str(root))
        # Default patterns still active
        assert is_ignored("__pycache__/cache.pyc", spec) is True
        assert is_ignored(".git/config", spec) is True

    def test_no_gitignore_defaults_only(self, make_project):
        root = make_project({"app.py": "x = 1\n"})
        spec = build_spec(str(root))
        # Defaults should still work
        assert is_ignored(".git/config", spec) is True
        assert is_ignored("node_modules/pkg/index.js", spec) is True


# ---------------------------------------------------------------------------
# extra_exclude
# ---------------------------------------------------------------------------

class TestExtraExclude:
    def test_extra_exclude_pattern(self, make_project):
        root = make_project({
            "app.py": "x = 1\n",
            "test_app.py": "assert True\n",
        })
        spec = build_spec(str(root), extra_exclude=["test_*.py"])
        assert is_ignored("test_app.py", spec) is True
        assert is_ignored("app.py", spec) is False

    def test_extra_exclude_dir(self, make_project):
        root = make_project({
            "app.py": "x = 1\n",
            "docs/README.md": "# Docs\n",
        })
        spec = build_spec(str(root), extra_exclude=["docs/"])
        assert is_ignored("docs/README.md", spec) is True
        assert is_ignored("app.py", spec) is False

    def test_extra_exclude_combined_with_defaults(self, make_project):
        root = make_project({"app.py": ""})
        spec = build_spec(str(root), extra_exclude=["*.log"])
        # Custom
        assert is_ignored("debug.log", spec) is True
        # Default
        assert is_ignored(".git/config", spec) is True


# ---------------------------------------------------------------------------
# is_ignored — direct function tests
# ---------------------------------------------------------------------------

class TestIsIgnored:
    def test_matching_path(self, make_project):
        root = make_project({"a.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("__pycache__/m.pyc", spec) is True

    def test_non_matching_path(self, make_project):
        root = make_project({"a.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("src/main.py", spec) is False

    def test_nested_ignored_dir(self, make_project):
        root = make_project({"a.py": ""})
        spec = build_spec(str(root))
        assert is_ignored("project/.git/HEAD", spec) is True
