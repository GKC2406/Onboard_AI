#!/usr/bin/env python3
"""
One-command entry point for Onboard AI: Sheet → codebase index → Ollama → guide.
Usage:
  python scripts/run_onboard.py TASK-001 [codebase_path]
  python scripts/run_onboard.py TASK-001                    # use current dir as codebase
  python scripts/run_onboard.py TASK-001 /path/to/project    # index that project
Requires: credentials.json, sheet shared with service account, Ollama running (llama3).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_SHEET = "https://docs.google.com/spreadsheets/d/1W0yefAMKumwLq4VbsOHUHnpS4ksDRsVFrdgSP1ox_6s/edit#gid=0"


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_onboard.py TASK-001 [codebase_path]")
        print("  TASK-001 = task ID in your Google Sheet")
        print("  codebase_path = path to project to index (default: current directory)")
        return 1
    task_id = sys.argv[1].strip()
    codebase_root = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else ROOT

    from src.orchestration import run_pipeline
    from src.sheet_reader.config import get_credentials_path

    creds = get_credentials_path(ROOT)
    if not creds.is_file():
        print("credentials.json not found. Place it in project root.")
        return 1

    print(f"Running pipeline: task_id={task_id}, codebase={codebase_root}")
    print("Fetching task from sheet → indexing codebase → calling Ollama...\n")
    result = run_pipeline(
        task_id=task_id,
        sheet_url=DEFAULT_SHEET,
        codebase_root=codebase_root,
        credentials_path=creds,
    )

    if result.error:
        print(f"Error: {result.error}")
        return 1

    print(f"Task: [{result.task_id}] {result.task_title}\n")
    print("=== FILES TO TOUCH (in order) ===")
    for i, path in enumerate(result.files_ordered, 1):
        print(f"  {i}. {path}")
    print("\n=== STEP-BY-STEP GUIDE ===")
    print(result.steps_text or result.raw_guide_response[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
