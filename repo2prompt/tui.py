"""Interactive TUI file selector using Textual.

Gracefully degrades when textual is not installed -- calling launch_selector()
will print an error with installation instructions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._optional import require_optional
from .log import get_logger
from .scanner import Entry

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Tree filtering utility (no textual dependency)
# ---------------------------------------------------------------------------

def filter_tree(original: Entry, selected_paths: set[str]) -> Entry | None:
    """Build a new Entry tree containing only selected paths.

    Args:
        original: The root Entry tree.
        selected_paths: Set of relative paths (POSIX-style) of selected files.

    Returns:
        A new pruned Entry tree, or None if nothing is selected.
    """
    if not selected_paths:
        return None

    def _filter(entry: Entry) -> Entry | None:
        if not entry.is_dir:
            if entry.rel_path in selected_paths:
                return Entry(
                    name=entry.name,
                    rel_path=entry.rel_path,
                    is_dir=False,
                    children=[],
                )
            return None

        # Directory: keep if any descendant is selected
        new_children = []
        for child in entry.children:
            filtered = _filter(child)
            if filtered is not None:
                new_children.append(filtered)

        if new_children:
            return Entry(
                name=entry.name,
                rel_path=entry.rel_path,
                is_dir=True,
                children=new_children,
            )
        return None

    return _filter(original)


# ---------------------------------------------------------------------------
# TUI App (requires textual)
# ---------------------------------------------------------------------------

def _collect_files(entry: Entry) -> list[Entry]:
    """DFS-collect all file entries."""
    result = []
    if not entry.is_dir:
        return [entry]
    for child in entry.children:
        result.extend(_collect_files(child))
    return result


def launch_selector(tree: Entry, root_path: str) -> Entry | None:
    """Launch the interactive file selector TUI.

    Returns the filtered Entry tree, or None if the user cancelled.
    """
    require_optional("textual", "Interactive mode (-i)")

    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Header, Static, Tree as TextualTree

    class FileSelectorApp(App):
        """Interactive file selector for repo2prompt."""

        CSS = """
        #sidebar {
            width: 70%;
        }
        #info-panel {
            width: 30%;
            border-left: solid $primary;
            padding: 1;
        }
        """

        BINDINGS = [
            Binding("escape", "quit", "Quit", show=True),
        ]

        def __init__(self, root_entry: Entry, root_path: str) -> None:
            super().__init__()
            self._root_entry = root_entry
            self._root_path = root_path
            self._selected: set[str] = set()
            self._all_files: list[Entry] = _collect_files(root_entry)
            self._result: Entry | None = None

        def compose(self) -> ComposeResult:
            yield Header()
            with Horizontal():
                with Vertical(id="sidebar"):
                    yield TextualTree(self._root_entry.name, id="file-tree")
                with Vertical(id="info-panel"):
                    yield Static(self._make_info_text(), id="info")
            yield Footer()

        def on_mount(self) -> None:
            tree_widget = self.query_one("#file-tree", TextualTree)
            self._build_tree_nodes(tree_widget.root, self._root_entry)
            tree_widget.root.expand()

        def on_key(self, event) -> None:
            if event.key == "space":
                self.action_toggle()
                event.prevent_default()
            elif event.key == "enter":
                self.action_confirm()
                event.prevent_default()

        def _build_tree_nodes(self, parent_node, entry: Entry) -> None:
            for child in entry.children:
                if child.is_dir:
                    node = parent_node.add(f"[ ] {child.name}/", data=child)
                    self._build_tree_nodes(node, child)
                else:
                    label = f"[ ] {child.name}"
                    parent_node.add_leaf(label, data=child)

        def _make_info_text(self) -> str:
            total = len(self._all_files)
            selected = len(self._selected)
            return (
                f"Total files: {total}\n"
                f"Selected: {selected}\n\n"
                f"[Space] Toggle\n"
                f"[Enter] Confirm\n"
                f"[Escape] Quit"
            )

        def _update_info(self) -> None:
            info = self.query_one("#info", Static)
            info.update(self._make_info_text())

        def _toggle_children(self, node, entry: Entry, select: bool) -> None:
            """Recursively toggle all children of a directory."""
            for child_node in node.children:
                child_entry = child_node.data
                if child_entry is not None:
                    if child_entry.is_dir:
                        self._toggle_children(child_node, child_entry, select)
                    else:
                        if select:
                            self._selected.add(child_entry.rel_path)
                        else:
                            self._selected.discard(child_entry.rel_path)
                    # Update label
                    check = "x" if select else " "
                    suffix = "/" if child_entry.is_dir else ""
                    child_node.set_label(f"[{check}] {child_entry.name}{suffix}")

        def action_toggle(self) -> None:
            """Toggle selection of the focused node."""
            tree_widget = self.query_one("#file-tree", TextualTree)
            node = tree_widget.cursor_node
            if node is None or node.data is None:
                return

            entry = node.data
            if entry.is_dir:
                # Check if any child is selected
                any_selected = any(
                    f.rel_path in self._selected for f in _collect_files(entry)
                )
                new_select = not any_selected
                self._toggle_children(node, entry, new_select)
                check = "x" if new_select else " "
                node.set_label(f"[{check}] {entry.name}/")
            else:
                if entry.rel_path in self._selected:
                    self._selected.discard(entry.rel_path)
                    node.set_label(f"[ ] {entry.name}")
                else:
                    self._selected.add(entry.rel_path)
                    node.set_label(f"[x] {entry.name}")

            self._update_info()

        def action_confirm(self) -> None:
            """Confirm selection and exit."""
            self._result = filter_tree(self._root_entry, self._selected)
            self.exit()

        def action_quit(self) -> None:
            """Quit without confirming."""
            self._result = None
            self.exit()

    # Check if stdout is a TTY
    import sys
    if not sys.stdin.isatty():
        logger.error("Interactive mode requires a terminal (TTY).")
        print("Error: Interactive mode (-i) requires a terminal.", file=sys.stderr)
        sys.exit(1)

    app = FileSelectorApp(tree, root_path)
    app.run()
    return app._result
