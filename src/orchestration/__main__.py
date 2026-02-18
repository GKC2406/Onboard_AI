"""
CLI for Phase 4: full pipeline (sheet → index → Ollama → guide).
  python -m src.orchestration --task-id TASK-001 --sheet <URL> --codebase-root .
"""

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


# Default sheet URL for this project
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1W0yefAMKumwLq4VbsOHUHnpS4ksDRsVFrdgSP1ox_6s/edit#gid=0"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Onboard AI pipeline: fetch task from sheet → index codebase → generate guide (Ollama)"
    )
    ap.add_argument("--task-id", "-t", required=True, help="Task ID in the sheet (e.g. TASK-001)")
    ap.add_argument("--sheet", "-s", default=DEFAULT_SHEET_URL, help="Google Sheet URL or key")
    ap.add_argument("--codebase-root", "-r", default=".", type=Path, help="Path to codebase to index")
    ap.add_argument("--credentials", "-c", help="Path to credentials.json")
    ap.add_argument("--model", "-m", default="llama3", help="Ollama model")
    ap.add_argument("--ollama-host", help="Ollama host (default: localhost)")
    ap.add_argument("--json", action="store_true", help="Output result as JSON")
    args = ap.parse_args()

    result = run_pipeline(
        task_id=args.task_id,
        sheet_url=args.sheet,
        codebase_root=args.codebase_root,
        credentials_path=args.credentials,
        ollama_model=args.model,
        ollama_host=args.ollama_host,
    )

    if result.error:
        if args.json:
            print(json.dumps({"error": result.error, "task_id": result.task_id}, indent=2))
        else:
            print(f"Error: {result.error}")
        raise SystemExit(1)

    if args.json:
        out = {
            "task_id": result.task_id,
            "task_title": result.task_title,
            "task_description": result.task_description,
            "files_ordered": result.files_ordered,
            "steps_text": result.steps_text,
        }
        print(json.dumps(out, indent=2))
        return

    print(f"Task: [{result.task_id}] {result.task_title}")
    print(f"Description: {result.task_description[:200]}{'...' if len(result.task_description) > 200 else ''}")
    print()
    print("=== FILES TO TOUCH (in order) ===")
    for i, path in enumerate(result.files_ordered, 1):
        print(f"  {i}. {path}")
    print()
    print("=== STEP-BY-STEP GUIDE ===")
    print(result.steps_text or result.raw_guide_response[:1500])


if __name__ == "__main__":
    main()
