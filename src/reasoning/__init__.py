"""
Phase 3: Reasoning layer (Ollama).
Given a task + codebase index, produces a step-by-step guide and ordered list of files to touch.
"""

from .task_guide import generate_task_guide, TaskGuideResult

__all__ = ["generate_task_guide", "TaskGuideResult"]
