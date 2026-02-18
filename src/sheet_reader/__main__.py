"""
CLI for Phase 2: read tasks from Google Sheet.
  python -m src.sheet_reader --sheet <URL_OR_KEY> [--task-id TASK_ID] [--assignee NAME] [--credentials PATH]
"""

import argparse
import json
from pathlib import Path

from .config import get_credentials_path
from .reader import SheetTaskReader


def main() -> None:
    ap = argparse.ArgumentParser(description="Read tasks from Google Sheet (credentials.json)")
    ap.add_argument("--sheet", "-s", required=True, help="Sheet URL or key")
    ap.add_argument("--task-id", "-t", help="Get task by ID")
    ap.add_argument("--assignee", "-a", help="List tasks for assignee")
    ap.add_argument("--worksheet", "-w", type=int, default=0, help="Worksheet index (default 0)")
    ap.add_argument("--credentials", "-c", help="Path to credentials.json (default: project root)")
    ap.add_argument("--json", action="store_true", help="Output as JSON")
    args = ap.parse_args()

    creds_path = Path(args.credentials) if args.credentials else get_credentials_path()
    reader = SheetTaskReader(credentials_path=creds_path)

    try:
        if args.task_id:
            task = reader.get_task_by_id(args.sheet, args.task_id, args.worksheet)
            if task is None:
                print(f"No task found with id: {args.task_id}")
                return
            out = {
                "task_id": task.task_id,
                "assignee": task.assignee,
                "title": task.title,
                "description": task.description,
                "status": task.status,
            }
            if args.json:
                print(json.dumps(out, indent=2))
            else:
                print(f"Task ID: {task.task_id}")
                print(f"Assignee: {task.assignee}")
                print(f"Title: {task.title}")
                print(f"Description: {task.description}")
                print(f"Status: {task.status}")
        elif args.assignee:
            tasks = reader.get_tasks_for_assignee(args.sheet, args.assignee, args.worksheet)
            out = [
                {"task_id": t.task_id, "assignee": t.assignee, "title": t.title, "description": t.description, "status": t.status}
                for t in tasks
            ]
            if args.json:
                print(json.dumps(out, indent=2))
            else:
                for t in tasks:
                    print(f"- [{t.task_id}] {t.title} (assignee: {t.assignee}, status: {t.status})")
        else:
            tasks = reader.get_all_tasks(args.sheet, args.worksheet)
            out = [
                {"task_id": t.task_id, "assignee": t.assignee, "title": t.title, "description": t.description, "status": t.status}
                for t in tasks
            ]
            if args.json:
                print(json.dumps(out, indent=2))
            else:
                print(f"Total tasks: {len(tasks)}")
                for t in tasks:
                    print(f"  [{t.task_id}] {t.title} | {t.assignee} | {t.status}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
