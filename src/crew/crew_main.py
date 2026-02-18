"""
CrewAI integration for Onboard AI.

Agents:
- Sheet Agent: fetches task details from Google Sheet.
- Parser Agent: indexes the codebase and summarizes structure.
- Reasoning Agent: plans and generates step-by-step guides.
- Verification Agent: reviews and improves the guide.

Key Agentic Features:
- Dynamic Tool Usage: Agents can read files and search code
- Error Handling: Handles task not found gracefully
- Caching: Index caching to avoid repeated scans
- Configurable verbosity
"""

from pathlib import Path
from typing import Optional
import hashlib
import json

from crewai import Agent, Crew, Task
from crewai.tools import tool
from crewai import LLM

from src.sheet_reader import SheetTaskReader
from src.sheet_reader.config import get_credentials_path
from src.parser import scan_project, build_index, format_index_for_llm


# === Configuration ===
# #/Users/gc/Desktop/Onboard_AI/src/index_cache/.onboard_cache
INDEX_CACHE_DIR = Path(__file__).parent.parent.parent / "src/index_cache/.onboard_cache"      
# INDEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# === Caching Utilities ===

def _get_cache_path(root: Path) -> Path:
    """Get cache file path for a codebase root."""
    root_hash = hashlib.md5(str(root.resolve()).encode()).hexdigest()
    return INDEX_CACHE_DIR / f"index_{root_hash}.json"


def _get_cached_index(root: Path, max_files: int = 300) -> Optional[str]:
    """Try to load cached index. Returns None if cache is stale or missing."""
    cache_path = _get_cache_path(root)
    if not cache_path.exists():
        return None
    
    # Check if cache is older than root directory
    try:
        root_mtime = root.stat().st_mtime
        cache_mtime = cache_path.stat().st_mtime
        
        if cache_mtime < root_mtime:
            # Root was modified after cache - invalidate
            return None
        
        with open(cache_path) as f:
            data = json.load(f)
        return format_index_for_llm(data, max_files=max_files)
    except Exception:
        return None


def _save_cache(root: Path, index_data: dict) -> None:
    """Save index to cache."""
    cache_path = _get_cache_path(root)
    try:
        with open(cache_path, "w") as f:
            json.dump(index_data, f)
    except Exception:
        pass  # Non-critical if caching fails


# === Tools wrapping existing functionality ===

@tool("get_task_from_sheet")
def get_task_from_sheet(task_id: str, sheet_url: str) -> str:
    """
    Fetch a task from the Google Sheet.

    REQUIRED INPUT example (flat JSON only):
    {
      "task_id": "<string>",
      "sheet_url": "<string>"
    }

    Do NOT wrap inputs inside 'properties'.
    """
    reader = SheetTaskReader(credentials_path=get_credentials_path())
    task = reader.get_task_by_id(sheet_url, task_id)
    if not task:
        return f'{{"error": "TASK_{task_id}_NOT_FOUND in sheet {sheet_url}"}}'
    # Simple JSON-ish string (model can parse it)
    return (
        "{"
        f"\"task_id\": \"{task.task_id}\", "
        f"\"assignee\": \"{task.assignee}\", "
        f"\"title\": \"{task.title}\", "
        f"\"description\": \"{task.description}\", "
        f"\"status\": \"{task.status}\""
        "}"
    )


@tool("index_codebase")
def index_codebase(root: str, use_cache: bool = True) -> str:
    """
    Scan a codebase root and return a human-readable summary (file tree, file list).
    
    Uses caching to avoid repeated scans. Set use_cache=False to force re-index.
    """
    root_path = Path(root).resolve()
    
    # Try cache first (unless disabled)
    if use_cache:
        cached = _get_cached_index(root_path)
        if cached:
            return "[CACHED] " + cached
    
    files = scan_project(root_path)
    index = build_index(files)
    
    # Save to cache
    _save_cache(root_path, index)
    
    return format_index_for_llm(index, max_files=300)


@tool("read_file")
def read_file(file_path: str) -> str:
    """
    Read the contents of a specific file from the codebase.
    Use this when you need to understand the actual code in a file.

    REQUIRED INPUT EXAMPLE (flat JSON with a real path value, NOT a placeholder):
    {
      "file_path": "/Users/you/myproject/src/file_name"
    }
    Above is just an example

    IMPORTANT: Only use paths that were listed in a previous task output. Try each file only ONCE.
    If not found, accept it and move on immediately. Do not retry.
    """
    path = Path(file_path)
    
    # Try relative to current directory, or absolute
    if not path.is_file():
        path = Path.cwd() / file_path
    
    if not path.is_file():
        return f'{{"error": "FILE_NOT_FOUND: {file_path}"}}'
    
    try:
        # Limit file size to avoid huge outputs
        content = path.read_text()
        if len(content) > 10000:
            content = content[:10000] + f"\n\n... (truncated, total {len(content)} chars)"
        return f"=== FILE: {path.name} ===\n{content}"
    except Exception as e:
        return f'{{"error": "Failed to read file: {str(e)}"}}'


@tool("search_codebase")
def search_codebase(root: str, pattern: str, file_pattern: str = "*.py") -> str:
    """
    Search for a pattern in code files within the codebase.

    REQUIRED INPUT example (flat JSON with real values, NOT a schema):
    {
      "root": "/absolute_path/to/codebase",
      "pattern": "<search string, e.g. 'def login' or 'import axios'>",
      "file_pattern": "<file extension filter, e.g. '*.py' or '*.js' or '*.jsx'>"
    }

    CORRECT example:
      Action Input: {"root": "/home/user/myproject", "pattern": "def xyz", "file_pattern": "*.py"}
    WRONG example (do NOT do this):
      Action Input: {"properties": {"root": {"type": "string"}, ...}}

    IMPORTANT: root must be the exact absolute path you were given. Do not guess or invent it.
    pattern must be a non-empty search string. Do not pass an empty string for pattern.
    """
    # Directories to always exclude from search
    EXCLUDED_DIRS = {
        ".venv", "venv", "env", ".env",
        "node_modules", "__pycache__", ".git",
        ".mypy_cache", ".pytest_cache", ".ruff_cache",
        "dist", "build", ".eggs", "*.egg-info",
    }

    root_path = Path(root).resolve()
    matches = []

    try:
        for path in root_path.rglob(file_pattern):
            # Skip any file whose path contains an excluded directory
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            if path.is_file():
                try:
                    content = path.read_text()
                    for i, line in enumerate(content.splitlines(), 1):
                        # Simple substring match
                        if pattern.lower() in line.lower():
                            rel_path = path.relative_to(root_path)
                            matches.append(f"{rel_path}:{i}: {line.strip()}")
                except Exception:
                    pass
    except Exception as e:
        return f'{{"error": "Search failed: {str(e)}"}}'

    if not matches:
        return f'{{"result": "No matches found for pattern: {pattern}"}}'

    # Limit results
    if len(matches) > 50:
        matches = matches[:50] + [f"... ({len(matches) - 50} more matches)"]

    return "=== SEARCH RESULTS ===\n" + "\n".join(matches)


@tool("list_tasks_in_sheet")
def list_tasks_in_sheet(sheet_url: str) -> str:
    """
    List all available tasks in the Google Sheet. Use this to find valid task IDs
    when you're unsure what tasks exist.
    
    REQUIRED INPUT:
    {
      "sheet_url": "<string>"
    }
    """
    reader = SheetTaskReader(credentials_path=get_credentials_path())
    tasks = reader.get_all_tasks(sheet_url)
    
    if not tasks:
        return '{"result": "NO_TASKS found in sheet"}'
    
    task_list = []
    for t in tasks:
        task_list.append(f"- {t.task_id}: {t.title} (assignee: {t.assignee}, status: {t.status})")
    
    return "=== AVAILABLE TASKS ===\n" + "\n".join(task_list)


# === Crew Builder ===

def _make_llm(model: str = "llama3") -> LLM:
    """Create the shared CrewAI LLM that talks to Ollama."""
    # CrewAI expects the model name as "ollama/<model_name>"
    return LLM(model=f"ollama/{model}")


def build_crew(
    task_id: str,
    sheet_url: str,
    codebase_root: str | Path,
    *,
    model: str = "llama3",
    verbose: bool = False,
) -> Crew:
    """
    Build a Crew that runs the end-to-end onboarding flow for a task.
    
    Key Agentic Features:
    - Dynamic Tool Usage: Parser and Reasoning agents can read files and search code
    - verbose: If True, shows detailed debug output. If False, minimal output for users.
    - Caching: Index caching to avoid repeated scans
    """
    llm = _make_llm(model=model)
    codebase_root_str = str(Path(codebase_root).resolve())

    # === Sheet Agent ===
    sheet_agent = Agent(
        role="Sheet Agent",
        goal="Fetch accurate task details from the Google Sheet.",
        backstory=(
            "You are a deterministic data retrieval agent responsible ONLY for fetching "
            "task information from a Google Sheet.\n\n"

            "Your responsibilities:\n"
            "- Fetch task details by exact task_id using get_task_from_sheet.\n"
            "- If the task is not found, clearly report that the task does not exist.\n"
            "- If asked, list all available task IDs using list_tasks_in_sheet.\n\n"

            "Strict rules:\n"
            "- Do NOT infer, guess, or fabricate task details.\n"
            "- Do NOT modify task content or add interpretation.\n"
            "- Do NOT proceed if the task is not found.\n"
            "- Do NOT use any tools other than get_task_from_sheet or list_tasks_in_sheet.\n\n"

            "Your output must be factual, concise, and based only on sheet data."
        ),

        tools=[get_task_from_sheet, list_tasks_in_sheet],
        llm=llm,
        verbose=verbose,
    )

    # === Parser Agent (Enhanced with file reading and search) ===
    parser_agent = Agent(
        role="Parser Agent",
        goal="Understand the project structure and surface relevant files.",
        backstory=(
            "You are a codebase indexing and structure analysis agent.\n\n"

            "Your responsibilities:\n"
            "- Analyze the repository structure using index_codebase.\n"
            "- Identify which files are likely relevant to the given task based on "
            "file names, directories, and high-level purpose.\n\n"

            "Strict rules:\n"
            "- Do NOT read file contents unless absolutely necessary.\n"
            "- Prefer reasoning from file paths and directory structure first.\n"
            "- Do NOT guess file contents.\n"
            "- Do NOT invent files that are not present in the index.\n"
            "- Do NOT repeatedly search for generic patterns.\n\n"
            "- STOP if there is no structured list returned by the Parser.\n"

            "Your output should be a short, focused list of real file paths with a brief "
            "reason why each file might be relevant to the task."
        ),

        tools=[index_codebase, read_file, search_codebase],
        llm=llm,
        verbose=verbose,
    )

    # === Reasoning Agent (Enhanced with file access) ===
    reasoning_agent = Agent(
        role="Reasoning Agent",
        goal="Plan and generate clear, actionable step-by-step guides.",
        backstory=(
            "You are a senior reasoning and planning agent in a multi-agent system.\n\n"

            "CRITICAL MENTAL MODEL:\n"
            "Task express INTENT, not search queries.\n"
            "You must NEVER directly reuse task text, examples, or instructions "
            "as search patterns or file paths.\n\n"

            "MANDATORY REASONING STEPS (ALWAYS IN THIS ORDER):\n"
            "1. INTENT EXTRACTION (NO TOOLS):\n"
            "   - Paraphrase the task into a short intent statement in your head.\n"
            "   - Identify what TYPE of change is requested (e.g. contract, validation, logic, docs).\n"
            "   - Identify what KIND of files would logically contain such changes "
            "     (e.g. parser, schema, validator, config).\n\n"

            "2. SIGNAL DERIVATION (NO TOOLS):\n"
            "   - Convert intent into ABSTRACT SIGNALS, not literal strings.\n"
            "   - Signals may include:\n"
            "     • directory roles (parser/, schema/, validator/)\n"
            "     • file roles (indexing, output formatting, contracts)\n"
            "     • language types (.py, .ts, .json)\n"
            "   - NEVER derive signals from examples shown in instructions.\n\n"

            "3. TOOL DECISION GATE:\n"
            "   - Use a tool ONLY if it is strictly required to confirm or disambiguate.\n"
            "   - If no signal clearly maps to a file, STOP and report insufficiency.\n\n"

            "STRICT TOOL USAGE RULES:\n"
            "- NEVER use task text or examples as search patterns.\n"
            "- NEVER search for words like 'login', 'example', or sample file names "
            "  unless they appear in real code paths from the index.\n"
            "- NEVER invent file paths or file names.\n"
            "- NEVER retry the same tool call with the same input.\n\n"

            "FAILURE BEHAVIOR (VERY IMPORTANT):\n"
            "- If no relevant files are confidently identified, explicitly state:\n"
            "  'No relevant files can be identified for this task based on the codebase.'\n"
            "- DO NOT hallucinate to complete the task.\n"
            "- Stopping is a correct and successful outcome.\n\n"

            "Your goal is correctness and safety, NOT task completion at all costs."
        ),

        tools=[read_file, search_codebase],
        llm=llm,
        verbose=verbose,
        max_iter=8,
    )

    # === Verification Agent ===
    verification_agent = Agent(
        role="Verification Agent",
        goal="Critically review guides and improve their quality.",
        backstory=(
            "You are a senior code reviewer and quality auditor.\n\n"

            "Your responsibilities:\n"
            "- Review the generated guide for correctness and completeness.\n"
            "- Check that referenced files actually exist and make sense.\n"
            "- Identify missing steps, incorrect assumptions, or vague instructions.\n\n"

            "CRITICAL TOOL USAGE RULES:\n"
            "- Use ONLY ONE tool at a time. Never call multiple tools in a single response. "
            "- Output format must be a single flat JSON object: {\"key\": \"value\"}\n"
            "- Do NOT output an array of objects like [{},{}] - this will cause errors.\n"
            "- Wait for the tool result before deciding your next action.\n\n"

            "Strict rules:\n"
            "- Do NOT rewrite the entire guide unless necessary.\n"
            "- Do NOT introduce new files or steps that were not previously identified.\n"
            "- Use read_file only to verify claims made in the guide.\n"
            "- Do NOT re-run broad searches.\n"
            "- If something cannot be verified, clearly say so instead of guessing.\n\n"

            "Your goal is to improve accuracy and clarity, not to expand scope."
        ),

        tools=[read_file, search_codebase],
        llm=llm,
        verbose=verbose,
        max_iter=6,
    )

    # Task 1: Fetch task
    fetch_task = Task(
        description=(
            f"Use the get_task_from_sheet tool to fetch full details for task_id "
            f"'{task_id}' from sheet '{sheet_url}'. Return them clearly.\n\n"
            "If the tool returns an error (task not found), use list_tasks_in_sheet "
            "to see available task IDs and report which ones exist."
        ),
        agent=sheet_agent,
        expected_output="The task details (id, assignee, title, description, status) or an error message.",
        max_retries=1,
    )

    # Task 2: Index the codebase (with caching)
    index_codebase_task = Task(
        description=(
            f"You are working on task '{task_id}'. "
            f"Use the index_codebase tool to analyze the codebase at '{codebase_root_str}'. "
            f"Call it with: {{\"root\": \"{codebase_root_str}\", \"use_cache\": true}}\n\n"
            f"After getting the summary, identify which files are relevant to THIS specific task. "
            f"Base your file selection on the task title and description from the previous step — "
            f"do NOT default to generic patterns like 'login' or 'auth' unless the task is actually about those. "
            f"If you need to search for patterns, use search_codebase with root='{codebase_root_str}' "
            f"and a pattern derived from the actual task description."
        ),
        agent=parser_agent,
        # expected_output=(
        #     "A summary of the codebase structure with a list of files relevant "
        #     "to the specific task fetched in the previous step."
        # ),
        expected_output=(
            "Output MUST contain a section exactly titled:\n\n"
            "RELEVANT FILES:\n"
            "- <relative/path/to/file1>\n"
            "- <relative/path/to/file2>\n\n"
            "Inside angular brackets <> there will be path of the relevant files "
            "Examples shown in above instructions are illustrative only and must NEVER be treated as real file paths, search patterns, or candidate actions.\n"
            "Only list files that actually exist in the codebase index. "
            "Do NOT include explanations in this section."
        ),
        max_retries=1,
    )

    # Task 3: Read key files for context 
    read_relevant_files_task = Task(
        description=(
            f"You are working on task '{task_id}'. "
            f"The previous task MUST have produced a list of real file paths from the codebase at "
            f"'{codebase_root_str}'.\n\n"

            f"Your job:\n"
            f"- Look ONLY at the file paths explicitly listed in the previous task output.\n"
            f"- Select the files most relevant to the task description.\n\n"

            f"Tool usage rules:\n"
            f"- Call read_file using EXACT paths copied verbatim from the previous task output.\n"
            f"- Do NOT invent, infer, or guess file paths.\n"
            f"- Do NOT use example or placeholder paths.\n"
            f"- Try each file at most ONCE. If not found, move on immediately.\n\n"

            f"Failure handling:\n"
            f"- If the previous task output does NOT contain a clear file list, explicitly say:\n"
            f"  'No file list was provided by the Parser Agent. Cannot proceed.' and STOP."
        ),
        agent=reasoning_agent,
        expected_output=(
            "A list of file paths that were explicitly provided by the Parser Agent, "
            "each with a brief summary of relevant contents."
        ),
        max_retries=1,
    )

    # Task 4: Plan the task
    plan_tasks_task = Task(
        description=(
            f"You are working on task '{task_id}'. "
            f"Using the task title and description from Task 1, the codebase structure from Task 2, "
            f"and the file contents from Task 3, PLAN the exact implementation steps to complete THIS task. "
            f"Do NOT re-discover files — use only what was already found. "
            f"Do NOT default to generic steps — every step must be specific to the actual task description. "
            f"Be precise about what change is needed in each file and why."
        ),
        agent=reasoning_agent,
        expected_output=(
            "A numbered list of implementation steps specific to the task, "
            "each referencing an actual file and describing exactly what needs to be changed or added."
        ),
        max_retries=1,
    )

    # Task 5: Generate detailed guide
    generate_guide_task = Task(
        description=(
            "Using the plan and file list, write a detailed step-by-step guide "
            "for an intern to complete the task. Include:\n"
            "- A numbered list of files to inspect/modify, in order.\n"
            "- A numbered list of concrete steps, referencing those files.\n"
            "- Any specific code patterns or imports to look for.\n\n"
            "Reference actual code from files you've read to make the guide accurate."
        ),
        agent=reasoning_agent,
        expected_output=(
            "A numbered file list and a clear, actionable step-by-step guide."
        ),
        max_retries=1,
    )

    # Task 6: Verify the guide
    verify_guide_task = Task(
        description=(
            f"Critically review the generated guide. Identify any missing steps, "
            f"incorrect assumptions, or references to non-existent files.\n\n"
            f"If you need to verify a file exists, use read_file — but ONLY with file paths "
            f"that were explicitly listed in the guide from the previous task. "
            f"Do NOT invent or guess file paths. "
            f"If you need to search, use search_codebase tool with root='{codebase_root_str}'.\n\n"
            f"If needed, provide an improved or annotated version of the guide."
        ),
        agent=verification_agent,
        expected_output=(
            "A review of the guide plus an improved/annotated final guide."
        ),
        max_retries=1,
    )

# === Build the Crew ===
    crew = Crew(
        agents=[sheet_agent, parser_agent, reasoning_agent, verification_agent],
        tasks=[fetch_task, index_codebase_task, read_relevant_files_task, plan_tasks_task, generate_guide_task, verify_guide_task],
        verbose=verbose,
        tracing=True,  
    )
    
    return crew


def run_crew_for_task(
    task_id: str,
    sheet_url: str,
    codebase_root: str | Path,
    *,
    model: str = "llama3",
    verbose: bool = False,
) -> str:
    """
    Run the crew and return the final result.
    The result will contain the verification agent's final output (review + guide).
    Args:
        verbose: If True, shows detailed debug output. If False, minimal output.
    """
    crew = build_crew(
        task_id=task_id,
        sheet_url=sheet_url,
        codebase_root=codebase_root,
        model=model,
        verbose=verbose,
    )
    # Pass inputs to all tasks so agents know the actual values
    inputs = {
        "task_id": task_id,
        "sheet_url": sheet_url,
        "codebase_root": str(Path(codebase_root).resolve()),
    }

    result = crew.kickoff(inputs=inputs)

    # CrewAI typically returns a string summarizing the final task's output.
    return str(result)