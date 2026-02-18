"""
CLI for Phase 1: index a codebase.
  python -m src.parser --root /path/to/project [--output index.json] [--llm]
"""

import argparse
import json
from pathlib import Path

from .scanner import scan_project
from .index_builder import build_index, format_index_for_llm


def main() -> None:
    ap = argparse.ArgumentParser(description="Scan project and build codebase index")
    ap.add_argument("--root", "-r", default=".", help="Project root directory")
    ap.add_argument("--output", "-o", help="Write index JSON to file")
    ap.add_argument("--llm", action="store_true", help="Print LLM-formatted summary to stdout")
    ap.add_argument("--max-files", type=int, default=500, help="Max files in LLM summary")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Error: not a directory: {root}")
        return
    files = scan_project(root)
    index = build_index(files)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # FileInfo has path/relative_path etc; index has file_tree, files, by_extension
        with open(out_path, "w") as f:
            json.dump(index, f, indent=2)
        print(f"Wrote index ({index['total_files']} files) to {out_path}")
    if args.llm:
        print(format_index_for_llm(index, max_files=args.max_files))


if __name__ == "__main__":
    main()
