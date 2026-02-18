"""
Phase 4: Orchestration.
Single pipeline: Sheet (task_id) → codebase index → Ollama → guide.
"""

from .pipeline import run_pipeline, PipelineResult

__all__ = ["run_pipeline", "PipelineResult"]
