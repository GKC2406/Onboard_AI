#!/usr/bin/env python3
"""
Phase 1 test: run parser on this repo (Onboard_AI) and print tree + summary.
"""

import sys
from pathlib import Path

# Add project root so we can run: python scripts/test_phase1_parser.py
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.parser import scan_project, build_index, format_index_for_llm


def main():
    root = ROOT
    print(f"Scanning: {root}\n")
    files = scan_project(root)
    print(f"Found {len(files)} files\n")
    index = build_index(files)
    print("=== File tree ===")
    print(index["file_tree"])
    print("\n=== LLM summary (excerpt) ===")
    print(format_index_for_llm(index, max_files=50))


if __name__ == "__main__":
    main()
