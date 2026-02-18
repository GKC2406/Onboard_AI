"""
CrewAI-based multi-agent orchestration for Onboard AI.

This package wires your existing components (SheetTaskReader, parser,
reasoning) into CrewAI agents and tasks.
"""

from .crew_main import build_crew, run_crew_for_task

__all__ = ["build_crew", "run_crew_for_task"]

