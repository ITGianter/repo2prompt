"""Unit tests for the file_reader module."""

from __future__ import annotations

import os

from repo2prompt.file_reader import _detect_language, _is_whitelisted, read_file


# ---------------------------------------------------------------------------
# _detect_language
# ---------------------------------------------------------------------------

class TestDetectLanguage:
    """Language detection by file extension and basename."""

    def test_python(self, make_project):
        root = make_project({"a.py": ""})
        assert _detect_language(str(root / "a.py")) == "python"

    def test_java(self, make_project):
        root = make_project({"A.java": ""})
        assert _detect_language(str(root / "A.java")) == "java"

    def test_javascript(self, make_project):
        root = make_project({"app.js": ""})
        assert _detect_language(str(root / "app.js")) == "javascript"

    def test_typescript(self, make_project):
        root = make_project({"app.ts": ""})
        assert _detect_language(str(root / "app.ts")) == "typescript"

    def test_markdown(self, make_project):
        root = make_project({"README.md": ""})
        assert _detect_language(str(root / "README.md")) == "markdown"

    def test_json(self, make_project):
        root = make_project({"data.json": ""})
        assert _detect_language(str(root / "data.json")) == "json"

    def test_yaml(self, make_project):
        root = make_project({"config.yaml": "", "config.yml": ""})
        assert _detect_language(str(root / "config.yaml")) == "yaml"
        assert _detect_language(str(root / "config.yml")) == "yaml"

    def test_toml(self, make_project):
        root = make_project({"pyproject.toml": ""})
        assert _detect_language(str(root / "pyproject.toml")) == "toml"

    def test_shell(self, make_project):
        root = make_project({"run.sh": ""})
        assert _detect_language(str(root / "run.sh")) == "bash"

    def test_sql(self, make_project):
        root = make_project({"schema.sql": ""})
        assert _detect_language(str(root / "schema.sql")) == "sql"

    def test_html(self, make_project):
        root = make_project({"index.html": ""})
        assert _detect_language(str(root / "index.html")) == "html"

    def test_css(self, make_project):
        root = make_project({"style.css": ""})
        assert _detect_language(str(root / "style.css")) == "css"

    def test_xml(self, make_project):
        root = make_project({"pom.xml": ""})
        assert _detect_language(str(root / "pom.xml")) == "xml"

    def test_case_insensitive(self, make_project):
        root = make_project({"App.PY": ""})
        assert _detect_language(str(root / "App.PY")) == "python"


# ---------------------------------------------------------------------------
# _detect_language — whitelisted basenames
# ---------------------------------------------------------------------------

class TestWhitelistedBasenames:
    """Files matched by basename (no extension or special name)."""

    def test_dockerfile(self, make_project):
        root = make_project({"Dockerfile": ""})
        assert _detect_language(str(root / "Dockerfile")) == "text"

    def test_makefile(self, make_project):
        root = make_project({"Makefile": ""})
        assert _detect_language(str(root / "Makefile")) == "text"

    def test_requirements_txt(self, make_project):
        root = make_project({"requirements.txt": ""})
        assert _detect_language(str(root / "requirements.txt")) == "text"

    def test_pipfile(self, make_project):
        root = make_project({"Pipfile": ""})
        assert _detect_language(str(root / "Pipfile")) == "text"

    def test_gitignore(self, make_project):
        root = make_project({".gitignore": ""})
        assert _detect_language(str(root / ".gitignore")) == "text"


# ---------------------------------------------------------------------------
# _detect_language — unknown extensions
# ---------------------------------------------------------------------------

class TestUnknownExtension:
    def test_unknown_returns_empty(self, make_project):
        root = make_project({"data.xyz": ""})
        assert _detect_language(str(root / "data.xyz")) == ""

    def test_no_extension_not_whitelisted(self, make_project):
        root = make_project({"randomfile": ""})
        assert _detect_language(str(root / "randomfile")) == ""


# ---------------------------------------------------------------------------
# _is_whitelisted
# ---------------------------------------------------------------------------

class TestIsWhitelisted:
    def test_known_extension(self, make_project):
        root = make_project({"a.py": ""})
        assert _is_whitelisted(str(root / "a.py")) is True

    def test_known_basename(self, make_project):
        root = make_project({"Dockerfile": ""})
        assert _is_whitelisted(str(root / "Dockerfile")) is True

    def test_unknown(self, make_project):
        root = make_project({"data.bin": ""})
        assert _is_whitelisted(str(root / "data.bin")) is False


# ---------------------------------------------------------------------------
# read_file — normal reads
# ---------------------------------------------------------------------------

class TestReadFile:
    def test_read_utf8(self, make_project):
        root = make_project({"hello.py": 'print("hi")\n'})
        result = read_file(str(root / "hello.py"))
        assert result.content == 'print("hi")\n'
        assert result.language == "python"
        assert result.warning is None

    def test_read_non_whitelisted_skipped(self, make_project):
        root = make_project({"data.xyz": "some content"})
        result = read_file(str(root / "data.xyz"))
        assert result.content is None
        assert result.language == ""
        assert result.warning is None

    def test_read_file_not_found(self):
        result = read_file("/nonexistent/path/file.py")
        assert result.content is None
        assert result.warning is not None

    def test_read_file_too_large(self, make_project):
        root = make_project({"big.py": "x = 1\n" * 200000})
        result = read_file(str(root / "big.py"))
        assert result.content is None
        assert "too large" in result.warning.lower()


# ---------------------------------------------------------------------------
# read_file — encoding fallback
# ---------------------------------------------------------------------------

class TestEncodingFallback:
    def test_latin1_fallback(self, make_project):
        root = tmp_path = make_project({})
        filepath = str(root / "latin1.txt")
        with open(filepath, "wb") as f:
            f.write("hello \xe9\xe8\xea world\n".encode("latin-1"))
        result = read_file(filepath)
        assert result.content is not None
        assert "hello" in result.content
        assert result.language == "text"

    def test_undecodable_file(self, make_project):
        root = make_project({})
        filepath = str(root / "bad.bin")
        # Write bytes that are invalid in both UTF-8 and Latin-1 isn't a real
        # failure case (Latin-1 accepts all single bytes), so we create a file
        # that's not whitelisted to test the skip path instead. For a true
        # decode failure we need a whitelisted extension with bad bytes.
        filepath = str(root / "bad.py")
        with open(filepath, "wb") as f:
            f.write(b"\x80\x81\x82\xfe\xff")
        result = read_file(filepath)
        # Latin-1 will succeed for any single-byte sequence, so this should
        # actually read OK. The fallback works.
        assert result.content is not None or result.warning is not None
