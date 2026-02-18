"""
Read tasks from a Google Sheet by task_id or assignee.
Uses credentials.json (service account) for authentication.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gspread

from .config import get_credentials_path


@dataclass
class TaskRow:
    """A single task row from the sheet."""
    task_id: str
    assignee: str
    title: str
    description: str
    status: str
    raw_row: dict[str, Any]  # all columns as key -> value


class SheetTaskReader:
    """
    Reads tasks from a Google Sheet using service account credentials.
    Expects the sheet to have a header row; column names are configurable.
    """

    def __init__(
        self,
        credentials_path: str | Path | None = None,
        project_root: str | Path | None = None,
        *,
        task_id_col: str = "task_id",
        assignee_col: str = "assignee",
        title_col: str = "title",
        description_col: str = "description",
        status_col: str = "status",
    ):
        if credentials_path is None:
            credentials_path = get_credentials_path(project_root)
        self.credentials_path = Path(credentials_path)
        self.task_id_col = task_id_col
        self.assignee_col = assignee_col
        self.title_col = title_col
        self.description_col = description_col
        self.status_col = status_col
        self._client: gspread.Client | None = None

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            if not self.credentials_path.is_file():
                raise FileNotFoundError(
                    f"Credentials not found: {self.credentials_path}. "
                    "Place credentials.json in project root or set GOOGLE_APPLICATION_CREDENTIALS."
                )
            self._client = gspread.service_account(
                filename=str(self.credentials_path),
                scopes=gspread.auth.READONLY_SCOPES,
            )
        return self._client

    def open_sheet(self, sheet_key_or_url: str, worksheet_index: int = 0) -> gspread.Worksheet:
        """
        Open a spreadsheet by key (from URL) or full URL.
        Returns the first worksheet by default; use worksheet_index for others.
        """
        client = self._get_client()
        if sheet_key_or_url.startswith("http"):
            spreadsheet = client.open_by_url(sheet_key_or_url)
        else:
            spreadsheet = client.open_by_key(sheet_key_or_url)
        return spreadsheet.get_worksheet(worksheet_index)

    def _row_to_task(self, headers: list[str], row: list[Any]) -> TaskRow | None:
        raw = dict(zip(headers, row))
        task_id = raw.get(self.task_id_col, raw.get("Task ID", ""))
        if not str(task_id).strip():
            return None
        return TaskRow(
            task_id=str(task_id).strip(),
            assignee=str(raw.get(self.assignee_col, raw.get("Assignee", "")) or "").strip(),
            title=str(raw.get(self.title_col, raw.get("Title", "")) or "").strip(),
            description=str(raw.get(self.description_col, raw.get("Description", "")) or "").strip(),
            status=str(raw.get(self.status_col, raw.get("Status", "")) or "").strip(),
            raw_row=raw,
        )

    def get_all_tasks(
        self,
        sheet_key_or_url: str,
        worksheet_index: int = 0,
    ) -> list[TaskRow]:
        """Fetch all rows (header row required). Returns list of TaskRow."""
        ws = self.open_sheet(sheet_key_or_url, worksheet_index)
        rows = ws.get_all_values()
        if not rows:
            return []
        headers = [str(h).strip().lower().replace(" ", "_") for h in rows[0]]
        # Normalize our expected column names to possible header variants
        header_map = {h: h for h in headers}
        tasks = []
        for row in rows[1:]:
            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            raw = dict(zip(headers, row[: len(headers)]))
            task_id = raw.get("task_id") or raw.get("task id") or ""
            assignee = raw.get("assignee") or ""
            title = raw.get("title") or ""
            description = raw.get("description") or ""
            status = raw.get("status") or ""
            t = TaskRow(
                task_id=str(task_id).strip(),
                assignee=str(assignee).strip(),
                title=str(title).strip(),
                description=str(description).strip(),
                status=str(status).strip(),
                raw_row=raw,
            )
            if t.task_id:
                tasks.append(t)
        return tasks

    def get_task_by_id(
        self,
        sheet_key_or_url: str,
        task_id: str,
        worksheet_index: int = 0,
    ) -> TaskRow | None:
        """Return the first task row whose task_id matches (case-insensitive)."""
        tasks = self.get_all_tasks(sheet_key_or_url, worksheet_index)
        task_id_clean = str(task_id).strip().lower()
        for t in tasks:
            if t.task_id.lower() == task_id_clean:
                return t
        return None

    def get_tasks_for_assignee(
        self,
        sheet_key_or_url: str,
        assignee: str,
        worksheet_index: int = 0,
    ) -> list[TaskRow]:
        """Return all tasks where assignee matches (case-insensitive)."""
        tasks = self.get_all_tasks(sheet_key_or_url, worksheet_index)
        assignee_clean = str(assignee).strip().lower()
        return [t for t in tasks if t.assignee.lower() == assignee_clean]
