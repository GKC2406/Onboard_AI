"""
Phase 1: Project parser.
Scans a codebase and builds an index (file tree, file list with metadata)
for use by the reasoning layer.
"""

from .scanner import scan_project
from .index_builder import build_index, format_index_for_llm

__all__ = ["scan_project", "build_index", "format_index_for_llm"]
