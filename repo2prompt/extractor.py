"""Code structure outline extraction (skeleton mode).

Extracts class/function signatures and docstrings from source files.
Python uses the ast module; other languages use regex patterns.
"""

from __future__ import annotations

import ast
import os
import re
import textwrap
from dataclasses import dataclass, field

from .log import get_logger

logger = get_logger(__name__)


@dataclass
class OutlineItem:
    """A single structural element in a code outline."""
    kind: str          # "class", "function", "method"
    name: str
    signature: str     # e.g. "def process_data(self, input: str) -> dict:"
    docstring: str | None = None
    indent: int = 0    # indentation level (0 for top-level)


@dataclass
class CodeOutline:
    """Extracted skeleton of a source file."""
    items: list[OutlineItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Python extractor (ast-based)
# ---------------------------------------------------------------------------

def _format_annotation(node) -> str:
    """Best-effort reconstruction of a type annotation from AST."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return "..."


def _format_arguments(args: ast.arguments) -> str:
    """Reconstruct function arguments from AST."""
    try:
        return ast.unparse(args)
    except Exception:
        return "..."


def _extract_python_items(node: ast.AST, depth: int = 0) -> list[OutlineItem]:
    """Recursively extract class/function definitions from an AST node."""
    items: list[OutlineItem] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            sig = f"class {child.name}:"
            doc = ast.get_docstring(child)
            items.append(OutlineItem(kind="class", name=child.name, signature=sig, docstring=doc, indent=depth))
            items.extend(_extract_python_items(child, depth + 1))
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def" if isinstance(child, ast.AsyncFunctionDef) else "def"
            args_str = _format_arguments(child.args)
            ret = _format_annotation(child.returns)
            ret_part = f" -> {ret}" if ret else ""
            sig = f"{prefix} {child.name}({args_str}){ret_part}:"
            doc = ast.get_docstring(child)
            kind = "method" if depth > 0 else "function"
            items.append(OutlineItem(kind=kind, name=child.name, signature=sig, docstring=doc, indent=depth))
    return items


def extract_python_outline(content: str) -> CodeOutline:
    """Extract Python code outline using the ast module."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        logger.debug("Syntax error in Python file, falling back to regex")
        return extract_generic_outline(content, "python")
    return CodeOutline(items=_extract_python_items(tree))


# ---------------------------------------------------------------------------
# Generic regex extractor
# ---------------------------------------------------------------------------

_GENERIC_PATTERNS: dict[str, list[re.Pattern]] = {
    "javascript": [
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?class\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*const\s+(\w+)\s*=\s*(?:async\s+)?\(", re.MULTILINE),
    ],
    "typescript": [
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?interface\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?type\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*const\s+(\w+)\s*=\s*(?:async\s+)?\(", re.MULTILINE),
    ],
    "java": [
        re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*(?:public|private|protected)\s+[\w<>\[\],\s]+\s+(\w+)\s*\(", re.MULTILINE),
    ],
    "css": [
        re.compile(r"^([.#]?\w[\w\s,.#:>-]*?)\s*\{", re.MULTILINE),
    ],
    "default": [
        re.compile(r"^\s*(?:def|function|fn|func|pub fn|pub async fn)\s+(\w+)", re.MULTILINE),
        re.compile(r"^\s*class\s+(\w+)", re.MULTILINE),
    ],
}


def _find_line_number(content: str, match_start: int) -> int:
    """Get 1-based line number for a match position."""
    return content[:match_start].count("\n") + 1


def extract_generic_outline(content: str, language: str) -> CodeOutline:
    """Extract code outline using regex patterns for non-Python languages."""
    patterns = _GENERIC_PATTERNS.get(language, _GENERIC_PATTERNS["default"])
    items: list[OutlineItem] = []
    seen: set[str] = set()

    for pattern in patterns:
        for match in pattern.finditer(content):
            name = match.group(1).strip()
            if name in seen or not name:
                continue
            seen.add(name)
            # Get the full line as the signature
            line_start = content.rfind("\n", 0, match.start()) + 1
            line_end = content.find("\n", match.end())
            if line_end == -1:
                line_end = len(content)
            sig = content[line_start:line_end].strip()

            kind = "class" if "class" in sig.split(name)[0].lower() else "function"
            items.append(OutlineItem(kind=kind, name=name, signature=sig, indent=0))

    items.sort(key=lambda it: _find_line_number(content, content.find(it.signature)))
    return CodeOutline(items=items)


# ---------------------------------------------------------------------------
# Dispatcher and formatter
# ---------------------------------------------------------------------------

_PYTHON_LIKE = {"python"}
_REGEX_LANGS = {"javascript", "typescript", "java", "css"}


def extract_outline(content: str, language: str, rel_path: str) -> str:
    """Extract and format a code outline. Returns original content if language is unsupported."""
    if language in _PYTHON_LIKE:
        outline = extract_python_outline(content)
    elif language in _REGEX_LANGS:
        outline = extract_generic_outline(content, language)
    else:
        # Try default patterns as a fallback
        outline = extract_generic_outline(content, "default")
        if not outline.items:
            return content  # No structural elements found, return original

    if not outline.items:
        return content

    return _format_outline(outline, rel_path)


def _format_outline(outline: CodeOutline, rel_path: str) -> str:
    """Format a CodeOutline into a readable text block."""
    lines = [f"# --- Outline of {os.path.basename(rel_path)} ---"]
    for item in outline.items:
        prefix = "    " * item.indent
        lines.append(f"{prefix}{item.signature}")
        if item.docstring:
            doc_first = item.docstring.strip().split("\n")[0]
            lines.append(f'{prefix}    """{doc_first}"""')
        else:
            lines.append(f"{prefix}    ...")
    return "\n".join(lines)
