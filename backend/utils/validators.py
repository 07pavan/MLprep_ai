"""Security sandbox & validation utilities.

Provides:
  - validate_file()      — filename extension check
  - validate_dataframe() — non-empty DataFrame check
  - sanitize_code()      — regex-based dangerous pattern stripper
  - scan_guardrails()    — 3-layer prompt injection detector
"""
from __future__ import annotations
import re
import logging
import pandas as pd

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
# Code sanitizer (security sandbox — Layer 1)
# ---------------------------------------------------------------------------

BLOCKED_PATTERNS = [
    # OS / system access
    "os.", "sys.", "subprocess", "shutil.",
    # Inline imports of dangerous modules
    "import os", "import sys", "import subprocess", "import shutil",
    "import socket", "import urllib", "import requests", "import http",
    "import ctypes", "import signal", "import multiprocessing",
    # Code execution / reflection
    "eval(", "exec(", "__import__", "compile(",
    # Builtins / globals abuse
    "__builtins__", "globals()", "locals()", "vars(",
    "getattr(", "setattr(", "delattr(",
    # File I/O
    "open(", "file(", "io.open", "pathlib",
    # Dangerous builtins
    "breakpoint(", "__class__", "__bases__", "__subclasses__",
    "__mro__", "__dict__", "__code__",
    # Network
    "socket.", "urllib.", "requests.", "http.",
    # Process control
    "os.system", "os.popen", "os.exec",
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

        # Case-insensitive check against blocked patterns
        line_lower = line.lower()
        dangerous = any(pat.lower() in line_lower for pat in BLOCKED_PATTERNS)
        if dangerous:
            removed.append(stripped)
            safe_lines.append("# [SANITIZED]")
        else:
            safe_lines.append(line)

    if removed:
        logger.warning("sanitize_code() blocked %d line(s): %s", len(removed), removed)

    return "\n".join(safe_lines)


# ---------------------------------------------------------------------------
# Prompt guardrails (3-layer input defense — Layer 2)
# ---------------------------------------------------------------------------

# Maximum question length — truncate, don't crash
MAX_QUESTION_LENGTH = 2000

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?above",
        r"you\s+are\s+now\s+a",
        r"pretend\s+(you\s+are|to\s+be)",
        r"forget\s+(everything|all|your\s+(instructions|guidelines|rules))",
        r"disregard\s+(all|your|the)\s+(rules|instructions|guidelines)",
        r"act\s+as\s+(if|though|a\s+)\b",
        r"new\s+instruction[s]?\s*:",
        r"system\s*prompt\s*:",
        r"override\s+(your|the)\s+(rules|instructions)",
        r"do\s+not\s+follow\s+(your|the)\s+(rules|instructions)",
        r"reveal\s+(your|the)\s+(system|initial)\s+prompt",
        r"what\s+(is|are)\s+your\s+(system|initial)\s+(prompt|instructions)",
        r"repeat\s+(your|the)\s+(system|initial)\s+(prompt|instructions)",
        r"jailbreak",
        r"DAN\s+mode",
    ]
]

# Patterns that look like code/OS injection in natural language
_CODE_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"import\s+os\b",
        r"import\s+subprocess\b",
        r"os\.system\s*\(",
        r"subprocess\.(run|call|Popen)",
        r"rm\s+-rf\b",
        r"DROP\s+TABLE\b",
        r"DELETE\s+FROM\b",
        r";\s*--",
        r"UNION\s+SELECT\b",
    ]
]


def scan_guardrails(question: str) -> tuple[bool, str]:
    """
    Scan a user question for safety issues.

    Returns (True, "ok") if the question is safe.
    Returns (False, reason) if the question should be blocked.
    """
    # Layer 1 — Length & emptiness
    stripped = question.strip()
    if len(stripped) < 3:
        return False, "Question is too short. Please ask a complete question about your data."

    if len(stripped) > MAX_QUESTION_LENGTH:
        return False, (
            f"Question is too long ({len(stripped)} chars, max {MAX_QUESTION_LENGTH}). "
            "Please shorten your question."
        )

    # Layer 2 — Prompt injection detection
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(stripped):
            logger.warning("Guardrail BLOCKED (injection): %s", stripped[:100])
            return False, (
                "Your question was flagged as a potential prompt injection attempt. "
                "Please rephrase as a data analysis question."
            )

    # Layer 3 — Code/OS injection in natural language
    for pattern in _CODE_INJECTION_PATTERNS:
        if pattern.search(stripped):
            logger.warning("Guardrail BLOCKED (code injection): %s", stripped[:100])
            return False, (
                "Your question contains patterns that look like code injection. "
                "Please ask a natural language question about your data."
            )

    return True, "ok"
