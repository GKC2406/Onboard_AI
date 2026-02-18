"""
CLI for Phase 3: generate task guide from Ollama.
  python -m src.reasoning --task-title "..." --task-desc "..." --codebase-root /path [--model llama3]
  Or use --sheet and --task-id to load task from Google Sheet.
"""

import argparse
from pathlib import Path

from .task_guide import generate_task_guide

# Optional: Phase 1 parser and Phase 2 sheet reader
def _get_index_from_root(root: Path, max_files: int = 300) -> str:
    from src.parser import scan_project, build_index, format_index_for_llm
    files = scan_project(root)
    index = build_index(files)
    return format_index_for_llm(index, max_files=max_files)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate task guide (files + steps) using Ollama")
    ap.add_argument("--task-title", "-t", help="Task title")
    ap.add_argument("--task-desc", "-d", help="Task description")
    ap.add_argument("--codebase-root", "-r", default=".", type=Path, help="Project root to index")
    ap.add_argument("--codebase-index", help="Pre-built index text (file path or '-' for stdin); overrides --codebase-root")
    ap.add_argument("--sheet", "-s", help="Google Sheet URL or key (to fetch task by --task-id)")
    ap.add_argument("--task-id", "-i", help="Task ID in sheet (requires --sheet)")
    ap.add_argument("--model", "-m", default="llama3", help="Ollama model name")
    ap.add_argument("--ollama-host", help="Ollama host (default: localhost:11434)")
    ap.add_argument("--max-files", type=int, default=300, help="Max files in codebase context")
    args = ap.parse_args()

    title = args.task_title or ""
    description = args.task_desc or ""

    if args.sheet and args.task_id:
        try:
            from src.sheet_reader import SheetTaskReader
            from src.sheet_reader.config import get_credentials_path
            reader = SheetTaskReader(credentials_path=get_credentials_path())
            task = reader.get_task_by_id(args.sheet, args.task_id)
            if task:
                title = task.title
                description = task.description
                print(f"Loaded task from sheet: [{task.task_id}] {title}\n")
            else:
                print(f"No task found with id: {args.task_id}")
                return
        except Exception as e:
            print(f"Failed to load task from sheet: {e}")
            return

    if not title and not description:
        print("Provide --task-title and --task-desc, or --sheet and --task-id")
        return

    if args.codebase_index:
        if args.codebase_index == "-":
            import sys
            codebase_text = sys.stdin.read()
        else:
            codebase_text = Path(args.codebase_index).read_text()
    else:
        root = args.codebase_root.resolve()
        if not root.is_dir():
            print(f"Not a directory: {root}")
            return
        codebase_text = _get_index_from_root(root, args.max_files)

    print("Calling Ollama (this may take a moment)...\n")
    result = generate_task_guide(
        task_title=title,
        task_description=description,
        codebase_index_text=codebase_text,
        model=args.model,
        ollama_host=args.ollama_host,
    )

    print("=== FILES TO TOUCH (in order) ===")
    for i, path in enumerate(result.files_ordered, 1):
        print(f"  {i}. {path}")
    if not result.files_ordered:
        print("  (none parsed; see raw response below)")

    print("\n=== STEP-BY-STEP GUIDE ===")
    print(result.steps_text or "(see raw response below)")

    if not result.files_ordered and not result.steps_text:
        print("\n=== RAW RESPONSE ===")
        print(result.raw_response)


if __name__ == "__main__":
    main()
