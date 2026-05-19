"""Repo2Prompt - Convert local project structure and code into LLM-ready prompt text."""

import logging

__version__ = "0.1.0"

# Prevent "No handlers could be found" warnings when used as a library
logging.getLogger("repo2prompt").addHandler(logging.NullHandler())
