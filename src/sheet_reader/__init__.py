"""
Phase 2: Google Sheet task reader.
Reads tasks from a Google Sheet using service account credentials (credentials.json).
"""

from .config import get_credentials_path

# Lazy import so scripts can use get_credentials_path without requiring gspread
def __getattr__(name: str):
    if name in ("SheetTaskReader", "TaskRow"):
        from .reader import SheetTaskReader, TaskRow
        return SheetTaskReader if name == "SheetTaskReader" else TaskRow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["get_credentials_path", "SheetTaskReader", "TaskRow"]
