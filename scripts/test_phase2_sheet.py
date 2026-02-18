#!/usr/bin/env python3
"""
Phase 2 test: verify credentials path and (optionally) read from sheet.
Uses credentials.json from project root.
Run: python scripts/test_phase2_sheet.py [SHEET_URL_OR_KEY]
If no arg: only checks that credentials path exists.
If arg given: fetches all tasks from the sheet (requires: pip install -r requirements.txt).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.sheet_reader import get_credentials_path


def main():
    creds_path = get_credentials_path(ROOT)
    print(f"Using credentials: {creds_path}")
    if not creds_path.is_file():
        print("credentials.json not found. Place it in project root or set GOOGLE_APPLICATION_CREDENTIALS.")
        return 1
    print("Credentials file found.\n")

    if len(sys.argv) < 2:
        print("To test live: python scripts/test_phase2_sheet.py <SHEET_URL_OR_KEY>")
        print("Ensure the sheet is shared with the service account email from credentials.json")
        return 0

    try:
        from src.sheet_reader import SheetTaskReader
    except ModuleNotFoundError as e:
        print("Install dependencies first: pip install -r requirements.txt")
        print(f"(missing: {e})")
        return 1

    sheet_ref = sys.argv[1]
    reader = SheetTaskReader(credentials_path=creds_path)
    try:
        tasks = reader.get_all_tasks(sheet_ref)
        print(f"Tasks in sheet: {len(tasks)}")
        for t in tasks:
            print(f"  [{t.task_id}] {t.title} | {t.assignee} | {t.status}")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
