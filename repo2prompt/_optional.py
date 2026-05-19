"""Optional dependency checker with user-friendly error messages."""

from __future__ import annotations

import importlib
import sys


def require_optional(package_name: str, feature_name: str) -> None:
    """Check that an optional dependency is installed.

    Raises SystemExit with installation instructions if the package is missing.
    """
    try:
        importlib.import_module(package_name)
    except ImportError:
        print(
            f"Error: The '{feature_name}' feature requires '{package_name}'.\n"
            f"Install it with: pip install {package_name}",
            file=sys.stderr,
        )
        sys.exit(1)
