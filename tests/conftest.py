"""
conftest.py — Fixes Python path resolution for the test suite.

The project root contains stub 'utils/' and 'tools/' directories that shadow
the real implementations in 'backend/utils/' and 'backend/tools/'.
"""
import sys
import os
import pathlib
import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

def normalize(p):
    if not p:
        return ""
    return os.path.normcase(os.path.abspath(p))

norm_root = normalize(str(ROOT_DIR))
norm_backend = normalize(str(BACKEND_DIR))

def _sanitize_path():
    # Remove backend path if exists, and insert at 0
    global sys
    sys.path = [p for p in sys.path if normalize(p) != norm_backend]
    sys.path.insert(0, str(BACKEND_DIR))

    # Remove root-level directories, empty strings, dots, and CWD entries
    clean_path = []
    for p in sys.path:
        norm_p = normalize(p)
        if norm_p == norm_root or p == "" or p == ".":
            continue
        clean_path.append(p)
    sys.path = clean_path

    # Evict stale cached modules from root stubs
    STALE_PREFIXES = ("utils", "tools", "agents", "config")
    for mod_name in list(sys.modules.keys()):
        if any(mod_name == p or mod_name.startswith(p + ".") for p in STALE_PREFIXES):
            # Do not delete backend modules themselves if they are already correct
            mod = sys.modules[mod_name]
            file_path = getattr(mod, "__file__", "")
            if file_path and not normalize(file_path).startswith(norm_backend):
                del sys.modules[mod_name]

# Sanitize initially when conftest is loaded
_sanitize_path()

# Sanitize before every single test is executed to counter pytest's automatic path adjustments
def pytest_runtest_setup(item):
    _sanitize_path()
