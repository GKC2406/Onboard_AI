"""
End-to-end pipeline: fetch task from sheet → index codebase → generate guide with Ollama.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineResult:
    """Result of the full onboarding pipeline."""
    task_id: str
    task_title: str
    task_description: str
    files_ordered: list[str] = field(default_factory=list)
    steps_text: str = ""
    raw_guide_response: str = ""
    error: str | None = None


def run_pipeline(
    task_id: str,
    sheet_url: str,
    codebase_root: str | Path,
    *,
    credentials_path: str | Path | None = None,
    worksheet_index: int = 0,
    ollama_model: str = "llama3",
    ollama_host: str | None = None,
    max_index_files: int = 300,
) -> PipelineResult:
    """
    Run the full flow: load task from sheet → build codebase index → call Ollama → return guide.
    """
    from src.sheet_reader.config import get_credentials_path
    from src.sheet_reader.reader import SheetTaskReader
    from src.parser import scan_project, build_index, format_index_for_llm
    from src.reasoning import generate_task_guide
    from src.reasoning.task_guide import TaskGuideResult

    root = Path(codebase_root).resolve()
    creds = Path(credentials_path) if credentials_path else get_credentials_path(root)

    # 1. Fetch task from sheet
    reader = SheetTaskReader(credentials_path=creds)
    try:
        task = reader.get_task_by_id(sheet_url, task_id, worksheet_index)
    except Exception as e:
        return PipelineResult(
            task_id=task_id,
            task_title="",
            task_description="",
            error=f"Failed to load task from sheet: {e}",
        )
    if not task:
        return PipelineResult(
            task_id=task_id,
            task_title="",
            task_description="",
            error=f"Task '{task_id}' not found in sheet.",
        )

    # 2. Build codebase index
    if not root.is_dir():
        return PipelineResult(
            task_id=task_id,
            task_title=task.title,
            task_description=task.description,
            error=f"Codebase root is not a directory: {root}",
        )
    files = scan_project(root)
    index = build_index(files)
    codebase_text = format_index_for_llm(index, max_files=max_index_files)

    # 3. Generate guide with Ollama
    try:
        guide: TaskGuideResult = generate_task_guide(
            task_title=task.title,
            task_description=task.description,
            codebase_index_text=codebase_text,
            model=ollama_model,
            ollama_host=ollama_host,
        )
    except Exception as e:
        return PipelineResult(
            task_id=task_id,
            task_title=task.title,
            task_description=task.description,
            error=f"Ollama/reasoning failed: {e}",
        )

    return PipelineResult(
        task_id=task_id,
        task_title=task.title,
        task_description=task.description,
        files_ordered=guide.files_ordered,
        steps_text=guide.steps_text,
        raw_guide_response=guide.raw_response,
    )
