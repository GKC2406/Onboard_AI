#!/usr/bin/env python3
"""
Phase 3 test: generate a task guide using Ollama.
Usage:
  python scripts/test_phase3_reasoning.py
    -> uses a built-in sample task and this repo as codebase
  python scripts/test_phase3_reasoning.py --task-id TASK-001 --sheet URL
    -> fetches task from sheet, uses this repo as codebase
Requires: Ollama running (ollama serve) and a model (e.g. ollama pull llama3)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    # Default: sample task + this repo
    task_title = "Integrate login API with frontend"
    task_description = (
        "Connect the login form to the backend auth API at POST /api/auth/login. "
        "Handle success/error and store JWT in localStorage."
    )
    sheet_url = "https://docs.google.com/spreadsheets/d/1W0yefAMKumwLq4VbsOHUHnpS4ksDRsVFrdgSP1ox_6s/edit#gid=0"

    if "--task-id" in sys.argv:
        idx = sys.argv.index("--task-id")
        task_id = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        sheet = sys.argv[sys.argv.index("--sheet") + 1] if "--sheet" in sys.argv else sheet_url
        if task_id and sheet:
            from src.sheet_reader import SheetTaskReader
            from src.sheet_reader.config import get_credentials_path
            reader = SheetTaskReader(credentials_path=get_credentials_path(ROOT))
            task = reader.get_task_by_id(sheet, task_id)
            if task:
                task_title = task.title
                task_description = task.description
                print(f"Loaded from sheet: [{task.task_id}] {task_title}\n")
            else:
                print(f"Task {task_id} not found in sheet")
                return 1

    from src.parser import scan_project, build_index, format_index_for_llm
    from src.reasoning import generate_task_guide

    print("Building codebase index from this repo...")
    files = scan_project(ROOT)
    index = build_index(files)
    codebase_text = format_index_for_llm(index, max_files=200)
    print(f"Index: {len(files)} files\n")

    print("Calling Ollama...")
    try:
        result = generate_task_guide(
            task_title=task_title,
            task_description=task_description,
            codebase_index_text=codebase_text,
            model="llama3",
        )
    except ConnectionError as e:
        print(f"Ollama connection error: {e}")
        print("Ensure Ollama is running (ollama serve) and model is pulled (ollama pull llama3)")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

    print("\n=== FILES TO TOUCH (in order) ===")
    for i, path in enumerate(result.files_ordered, 1):
        print(f"  {i}. {path}")
    print("\n=== STEP-BY-STEP GUIDE ===")
    print(result.steps_text or result.raw_response[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
