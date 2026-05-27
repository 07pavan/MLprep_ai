"""Security sandbox & validation utilities"""
from __future__ import annotations
import re
import logging
import pandas as pd
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xls", ".json", ".parquet")


def validate_file(filename: str) -> tuple[bool, str]:
    """Validate uploaded file by filename."""
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        return False, (
            f"Unsupported file format. Supported formats: "
            f"{', '.join(ALLOWED_EXTENSIONS)}"
        )
    return True, "Valid"


def validate_dataframe(df: pd.DataFrame) -> tuple[bool, str]:
    """Validate that a dataframe is non-empty and has columns."""
    if df is None or df.empty:
        return False, "DataFrame is empty"
    if len(df) == 0:
        return False, "No rows in dataset"
    if len(df.columns) == 0:
        return False, "No columns in dataset"
    return True, "Valid"


# ---------------------------------------------------------------------------
# Code sanitizer (security sandbox)
# ---------------------------------------------------------------------------

BLOCKED_PATTERNS = [
    # OS / system access
    "os.", "sys.", "subprocess", "shutil.",
    # Inline imports of dangerous modules
    "import os", "import sys", "import subprocess", "import shutil",
    "import socket", "import urllib", "import requests", "import http",
    # Code execution / reflection
    "eval(", "exec(", "__import__", "compile(",
    # Builtins / globals abuse
    "__builtins__", "globals()", "locals()", "vars()",
    "getattr(", "setattr(", "delattr(", "hasattr(",
    # File I/O
    "open(", "file(", "io.open",
    # Dangerous builtins
    "breakpoint(", "__class__", "__bases__", "__subclasses__",
    # Network
    "socket.", "urllib.", "requests.",
]


def sanitize_code(code: str) -> str:
    """
    Strip dangerous patterns from LLM-generated code before exec().
    Dangerous lines are replaced with a comment so line numbers stay intact.
    """
    lines = code.split("\n")
    safe_lines: list[str] = []
    removed: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            safe_lines.append(line)
            continue

        dangerous = any(pat in line.lower() for pat in BLOCKED_PATTERNS)
        if dangerous:
            removed.append(stripped)
            safe_lines.append(f"# [SANITIZED] {stripped}")
        else:
            safe_lines.append(line)

    if removed:
        logger.warning("sanitize_code() blocked %d line(s): %s", len(removed), removed)

    return "\n".join(safe_lines)
