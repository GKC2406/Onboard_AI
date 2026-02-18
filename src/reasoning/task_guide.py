"""
Generate a task breakdown and file order using Ollama.
Given a task (title + description) and codebase index, returns a step-by-step guide
and which files to touch in what order.
"""

import re
from dataclasses import dataclass, field

from ollama import chat


@dataclass
class TaskGuideResult:
    """Result of task guide generation."""
    raw_response: str
    files_ordered: list[str] = field(default_factory=list)
    steps_text: str = ""


SYSTEM_PROMPT = """You are an expert onboarding assistant for new developers. Given a task and a codebase structure (file tree and file list), you produce:
1. An ordered list of file paths that the developer should look at or modify to complete the task (from the provided codebase only; use exact paths as shown).
2. A clear step-by-step guide to complete the task.

Be concise. Prefer files that are clearly relevant (e.g. config, API clients, components mentioned in the task). Order files by dependency or logical workflow (e.g. config first, then API layer, then UI)."""

USER_PROMPT_TEMPLATE = """## Task
**Title:** {title}

**Description:** {description}

## Codebase structure (reference only — suggest files from this list)
{codebase_index}

---
Respond with two sections:

**FILES TO TOUCH (in order):**
List each file path on its own line, numbered (1. path, 2. path, ...). Use only paths that appear in the codebase above.

**STEP-BY-STEP GUIDE:**
Numbered steps to complete the task. Be specific and reference the files you listed."""


def generate_task_guide(
    task_title: str,
    task_description: str,
    codebase_index_text: str,
    model: str = "llama3",
    ollama_host: str | None = None,
    max_context_chars: int = 12000,
) -> TaskGuideResult:
    """
    Call Ollama to generate a task breakdown and ordered file list.
    Requires Ollama running locally (e.g. ollama serve) and the model pulled (e.g. ollama pull llama3).
    """
    if len(codebase_index_text) > max_context_chars:
        codebase_index_text = codebase_index_text[:max_context_chars] + "\n\n... (truncated)"
    user_content = USER_PROMPT_TEMPLATE.format(
        title=task_title or "(no title)",
        description=task_description or "(no description)",
        codebase_index=codebase_index_text,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    if ollama_host:
        from ollama import Client
        client = Client(host=ollama_host)
        response = client.chat(model=model, messages=messages)
    else:
        response = chat(model=model, messages=messages)
    raw = (response.get("message") or {}).get("content") or ""

    files_ordered = _parse_files_section(raw)
    steps_text = _parse_steps_section(raw)

    return TaskGuideResult(
        raw_response=raw,
        files_ordered=files_ordered,
        steps_text=steps_text,
    )


def _parse_files_section(text: str) -> list[str]:
    """Extract numbered file paths from a 'FILES TO TOUCH' section."""
    files: list[str] = []
    # Look for section like "FILES TO TOUCH (in order):" or "**FILES TO TOUCH (in order):**"
    section = re.search(
        r"\*\*?FILES TO TOUCH.*?\*\*?\s*\n(.*?)(?=\n\s*\*\*?STEP|\n\s*$|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not section:
        # Fallback: lines that look like "1. path/to/file"
        for line in text.splitlines():
            m = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
            p = m.group(1).strip()
            if "/" in p or p.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".env")):
                files.append(p)
        return files
    block = section.group(1)
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\d+[.)]\s+(.+)$", line)
        if m:
            files.append(m.group(1).strip())
    return files


def _parse_steps_section(text: str) -> str:
    """Extract the STEP-BY-STEP GUIDE section."""
    section = re.search(
        r"\*\*?STEP-BY-STEP GUIDE\*\*?\s*\n(.*)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if section:
        return section.group(1).strip()
    return ""
