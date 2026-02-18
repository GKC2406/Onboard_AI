"""
CLI entrypoint for the CrewAI-based multi-agent flow.

Example:
  python -m src.crew --task-id TASK-001 --sheet "https://docs.google.com/..." --codebase-root .
  python -m src.crew --task-id TASK-001 --verbose  # for debug output
"""

import argparse
from pathlib import Path

from .crew_main import run_crew_for_task


DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1W0yefAMKumwLq4VbsOHUHnpS4ksDRsVFrdgSP1ox_6s/edit#gid=0"


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the CrewAI multi-agent onboarding flow for a task.")
    ap.add_argument("--task-id", "-t", required=True, help="Task ID in the Google Sheet (e.g. TASK-001)")
    ap.add_argument("--sheet", "-s", default=DEFAULT_SHEET_URL, help="Google Sheet URL or key")
    ap.add_argument("--codebase-root", "-r", default=".", type=Path, help="Path to the codebase to analyze")
    ap.add_argument("--model", "-m", default="llama3", help="Ollama model to use via LangChain ChatOllama")
    ap.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug output (useful for debugging)")
    args = ap.parse_args()

    root = args.codebase_root.resolve()
    print(f"Running CrewAI flow for task_id={args.task_id}, codebase={root}")
    print()
    final_output = run_crew_for_task(
        task_id=args.task_id,
        sheet_url=args.sheet,
        codebase_root=root,
        model=args.model,
        verbose=args.verbose,
    )
    print("=== FINAL OUTPUT ===")
    print(final_output)


if __name__ == "__main__":
    main()
