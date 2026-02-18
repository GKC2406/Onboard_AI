"""
Resolve path to Google service account credentials.json.
Looks in: env GOOGLE_APPLICATION_CREDENTIALS, project root, config/credentials.json.
"""

import os
from pathlib import Path


def get_credentials_path(project_root: str | Path | None = None) -> Path:
    """
    Return path to credentials.json for Google Sheets API (service account).
    Order: GOOGLE_APPLICATION_CREDENTIALS env, then project_root/credentials.json,
    then project_root/config/credentials.json, then cwd.
    """
    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    root = Path(project_root) if project_root else Path.cwd()
    candidates = [
        root / "credentials.json",
        root / "config" / "credentials.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return root / "credentials.json"  # default for clearer error if missing
