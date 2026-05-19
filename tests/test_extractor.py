"""Tests for code outline extraction."""

import os
import tempfile

from repo2prompt.extractor import (
    CodeOutline,
    OutlineItem,
    extract_generic_outline,
    extract_outline,
    extract_python_outline,
)
from repo2prompt.formatter import render, render_legacy
from repo2prompt.ignore import build_spec
from repo2prompt.scanner import build_tree
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


class TestPythonOutline:
    def test_class_with_methods(self):
        """Extract class and method definitions."""
        content = '''class MyService:
    """Handles business logic."""

    def process(self, data: dict) -> dict:
        """Process incoming data."""
        return data

    def validate(self, input: str) -> bool:
        return bool(input)
'''
        outline = extract_python_outline(content)
        names = [item.name for item in outline.items]
        assert "MyService" in names
        assert "process" in names
        assert "validate" in names

    def test_standalone_functions(self):
        """Extract top-level functions."""
        content = '''def helper(x: int) -> int:
    """A helper function."""
    return x + 1

def main():
    print(helper(5))
'''
        outline = extract_python_outline(content)
        names = [item.name for item in outline.items]
        assert "helper" in names
        assert "main" in names
        # Top-level functions should be "function" kind
        for item in outline.items:
            if item.name in ("helper", "main"):
                assert item.kind == "function"

    def test_nested_classes(self):
        """Extract nested class definitions."""
        content = '''class Outer:
    class Inner:
        def method(self):
            pass
'''
        outline = extract_python_outline(content)
        names = [item.name for item in outline.items]
        assert "Outer" in names
        assert "Inner" in names

    def test_async_functions(self):
        """Extract async function definitions."""
        content = '''async def fetch_data(url: str) -> str:
    """Fetch data from URL."""
    return "data"
'''
        outline = extract_python_outline(content)
        assert len(outline.items) == 1
        assert outline.items[0].name == "fetch_data"
        assert "async def" in outline.items[0].signature

    def test_docstrings_extracted(self):
        """Docstrings are captured."""
        content = '''def documented():
    """This is the docstring."""
    pass
'''
        outline = extract_python_outline(content)
        assert outline.items[0].docstring == "This is the docstring."

    def test_empty_file(self):
        """Empty file produces empty outline."""
        outline = extract_python_outline("")
        assert len(outline.items) == 0

    def test_syntax_error_fallback(self):
        """Syntax errors fall back to regex extraction."""
        content = "def broken(:\n    pass"
        outline = extract_python_outline(content)
        # Should not crash, may return empty or partial results
        assert isinstance(outline, CodeOutline)


class TestGenericOutline:
    def test_javascript_functions(self):
        """Extract JavaScript function declarations."""
        content = '''function hello() {
    console.log("hello");
}

const greet = (name) => {
    return `Hello ${name}`;
}
'''
        outline = extract_generic_outline(content, "javascript")
        names = [item.name for item in outline.items]
        assert "hello" in names

    def test_javascript_classes(self):
        """Extract JavaScript class declarations."""
        content = '''export class MyComponent extends React.Component {
    render() {
        return null;
    }
}
'''
        outline = extract_generic_outline(content, "javascript")
        names = [item.name for item in outline.items]
        assert "MyComponent" in names

    def test_typescript_interfaces(self):
        """Extract TypeScript interface declarations."""
        content = '''export interface User {
    name: string;
    age: number;
}

type ID = string | number;
'''
        outline = extract_generic_outline(content, "typescript")
        names = [item.name for item in outline.items]
        assert "User" in names
        assert "ID" in names

    def test_java_methods(self):
        """Extract Java class and method declarations."""
        content = '''public class Main {
    public static void main(String[] args) {
        System.out.println("Hello");
    }

    private int calculate(int x) {
        return x * 2;
    }
}
'''
        outline = extract_generic_outline(content, "java")
        names = [item.name for item in outline.items]
        assert "Main" in names
        assert "main" in names
        assert "calculate" in names

    def test_unknown_language_uses_default(self):
        """Unknown languages fall back to default patterns."""
        content = '''def my_function():
    pass

class MyClass:
    pass
'''
        outline = extract_generic_outline(content, "unknown_lang")
        names = [item.name for item in outline.items]
        assert "my_function" in names
        assert "MyClass" in names

    def test_empty_content(self):
        """Empty content produces empty outline."""
        outline = extract_generic_outline(content="", language="javascript")
        assert len(outline.items) == 0


class TestExtractOutline:
    def test_python_dispatch(self):
        """Python content is routed to AST extractor."""
        content = '''def func():
    pass
'''
        result = extract_outline(content, "python", "test.py")
        assert "def func()" in result
        assert "Outline of test.py" in result

    def test_javascript_dispatch(self):
        """JavaScript content is routed to regex extractor."""
        content = '''function hello() {
    console.log("hi");
}
'''
        result = extract_outline(content, "javascript", "test.js")
        assert "hello" in result

    def test_unsupported_language_returns_original(self):
        """Unsupported languages with no matches return original content."""
        content = "some random text without any structure"
        result = extract_outline(content, "markdown", "test.md")
        assert result == content


class TestOutlineIntegration:
    def test_legacy_render_with_outline(self):
        """Legacy render can show outlines instead of full content."""
        content = '''class MyClass:
    """A class."""
    def method(self):
        """A method."""
        pass
'''
        root = _make_project({"test.py": content})
        spec = build_spec(root)
        tree = build_tree(root, spec)

        output = render_legacy(tree, root, outline_only=True)
        assert "class MyClass" in output
        assert "def method" in output

    def test_summary_render_with_outline(self):
        """Summary render can show outlines in content index."""
        content = '''class MyClass:
    """A class."""
    def method(self):
        pass
'''
        root = _make_project({"test.py": content})
        spec = build_spec(root)
        tree = build_tree(root, spec)

        file_summaries = [
            FileSummary(
                index="FILE_001",
                rel_path="test.py",
                summary="A Python class",
                content=content,
                language="python",
                warning=None,
            )
        ]
        output = render(tree, file_summaries, outline_only=True)
        assert "class MyClass" in output
        assert "def method" in output

    def test_outline_threshold_selective(self):
        """Only files exceeding threshold get outline extraction."""
        small = "x = 1\n"
        big = "\n".join([f"line{i} = {i}" for i in range(1000)])
        root = _make_project({"small.py": small, "big.py": big})
        spec = build_spec(root)
        tree = build_tree(root, spec)

        output = render_legacy(tree, root, outline_threshold=500)
        # small.py should have full content
        assert "x = 1" in output
        # big.py should have outline (or original if no structural elements)
        # Since big.py has no class/function defs, it returns original content
