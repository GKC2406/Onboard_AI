# Onboard AI - Enhanced Agentic Architecture

## Table of Contents
1. [Project Flow](#project-flow)
2. [Architecture Before vs After](#architecture-before-vs-after)
3. [RAG Analysis - Why We're Using Hybrid Approach](#rag-analysis---why-were-using-hybrid-approach)
4. [Conditional Task Handling](#conditional-task-handling)
5. [Agent Capabilities](#agent-capabilities)

---

## Project Flow

```
User Request (TASK-001)
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                         │
│                    (CrewAI Multi-Agent)                         │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. SHEET AGENT                                                │
│     ├─ Tool: get_task_from_sheet(task_id, sheet_url)          │
│     └─ Tool: list_tasks_in_sheet(sheet_url) [fallback]         │
│     Output: Task details (id, title, description, assignee)   │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. PARSER AGENT                                               │
│     ├─ Tool: index_codebase(root, use_cache=True)              │
│     │   └─ Caching: ~/.onboard_cache/index_<hash>.json         │
│     ├─ Tool: read_file(file_path) [dynamic]                    │
│     └─ Tool: search_codebase(root, pattern, file_pattern)       │
│     Output: File tree + relevant files identified               │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. REASONING AGENT                                            │
│     ├─ Tool: read_file(file_path) [dynamic]                    │
│     ├─ Tool: search_codebase(root, pattern) [dynamic]          │
│     │                                                            │
│     │ 3a. Read Relevant Files Task                             │
│     │     → Agent decides which files to read                   │
│     │     → Reads actual code content                           │
│     │                                                            │
│     │ 3b. Plan Task                                             │
│     │     → Creates high-level plan                             │
│     │     → Identifies files to modify                          │
│     │                                                            │
│     │ 3c. Generate Guide Task                                   │
│     │     → Writes detailed step-by-step guide                  │
│     │     → References actual code from files read             │
│     Output: Draft guide with file list                          │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. VERIFICATION AGENT                                          │
│     ├─ Tool: read_file(file_path) [for verification]            │
│     ├─ Tool: search_codebase(root, pattern) [for verification] │
│     │                                                            │
│     │ Tasks:                                                     │
│     │   - Check guide correctness                               │
│     │   - Verify file paths exist                               │
│     │   - Validate code references                              │
│     │   - Improve/annotate guide                                │
│     Output: Final verified guide                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
    FINAL OUTPUT
```

---

## Architecture Before vs After

### BEFORE (Linear Pipeline)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Sheet     │───▶│   Parser    │───▶│  Reasoning  │───▶│   Output    │
│  (fetch)    │    │  (index)    │    │  (LLM call) │    │  (guide)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘

- Sequential execution
- Fixed flow (no branching)
- One LLM call
- No file reading (just indexing)
- No verification loop
- No error handling
```

### AFTER (Agentic Multi-Agent)

```
┌─────────────────────────────────────────────────────────────────┐
│                        SHEET AGENT                              │
│  ┌─────────────────┐  ┌─────────────────┐                     │
│  │get_task_from_   │  │list_tasks_in_    │                     │
│  │sheet (primary) │  │sheet (fallback) │                     │
│  └────────┬────────┘  └────────┬────────┘                     │
└───────────┼───────────────────┼────────────────────────────────┘
            │                   │
            ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PARSER AGENT                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │index_codebase│  │ read_file    │  │search_codebase│        │
│  │(with cache) │  │ (dynamic)    │  │ (dynamic)    │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     REASONING AGENT                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Dynamic Tool Usage: Agent decides WHAT to read/search  │  │
│  │  - Reads relevant files based on task                   │  │
│  │  - Searches for patterns in code                        │  │
│  │  - Plans steps based on actual code                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   VERIFICATION AGENT                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Self-Correction Loop:                                    │  │
│  │  - Reads files to verify guide accuracy                  │  │
│  │  - Searches to confirm code patterns                     │  │
│  │  - Improves guide if needed                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Improvements

| Feature | Before | After |
|---------|--------|-------|
| **Tool Usage** | Fixed (index only) | Dynamic (read, search, index) |
| **File Reading** | None | Agent decides which files to read |
| **Search** | None | Pattern-based code search |
| **Caching** | None | Index caching with auto-invalidation |
| **Error Handling** | None | Fallback to list tasks / manual input |
| **Verification** | None | Self-correction loop |
| **Agency** | Linear script | Multi-agent with delegation |

---

## RAG Analysis - Why We're Using Hybrid Approach

### Your Concern: "Will RAG cause memory and latency issues?"

You're absolutely right to be concerned. Here's the analysis:

### Problems with Traditional RAG for Codebases

1. **Chunking Issues**
   - Code has complex dependencies - splitting by file/function often breaks context
   - Class definitions span multiple chunks
   - Imports and dependencies span files

2. **Embedding Challenges**
   - Open-source vector DBs (Faiss, Chroma) need embeddings for EVERY chunk
   - Code embeddings are different from text embeddings
   - Semantic search on code is notoriously difficult

3. **Latency**
   - Embedding generation takes time
   - Vector search adds latency
   - Multiple LLM calls (retrieve + generate)

4. **Memory**
   - Large codebases = millions of chunks
   - Vector store can grow huge
   - Context window limits still apply

### Our Hybrid Approach (Better for Codebases)

Instead of full RAG, we use **Selective Retrieval with Agent Decision**:

```
Codebase
    │
    ├─ PHASE 1: Lightweight Index (No RAG)
    │   ├── File tree structure
    │   ├── File list with extensions
    │   └── Metadata (lines, size)
    │   
    │   → Fast to generate (scan only)
    │   → Small footprint (JSON, not vectors)
    │   → Cached for performance
    │
    └─ PHASE 2: Dynamic File Reading (When Needed)
        ├── Agent decides WHAT to read
        ├── Reads actual file content
        └── No embedding/vector needed
```

### Why This Works Better

| Aspect | Traditional RAG | Our Hybrid Approach |
|--------|----------------|---------------------|
| **Index Size** | Millions of vectors | ~few KB JSON |
| **Index Time** | Minutes (embedding) | Seconds (scan) |
| **Query Time** | Vector search + LLM | Agent decides + read |
| **Context** | Retrieved chunks | Full file content |
| **Accuracy** | Can miss context | Agent verifies by reading |

### When RAG IS Useful

RAG would be better for:
- Very large codebases (1000+ files)
- When you need semantic search ("find code similar to X")
- When you can't read all files due to time constraints

### Our Caching Strategy

```python
# Cache index to ~/.onboard_cache/
index_hash = md5(codebase_root)  # Unique per project
cache_file = f"index_{hash}.json"

# Auto-invalidate if codebase modified
if cache_mtime < root_mtime:
    regenerate_index()  # Fresh scan
```

---

## Conditional Task Handling

### Scenario: Task Not Found

```
User Input: TASK-999 (doesn't exist)
                    │
                    ▼
┌─────────────────────────────────────────┐
│  Sheet Agent calls get_task_from_sheet   │
│  Returns: {"error": "Task TASK-999..."} │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│  Agent detects error in output          │
│  → Calls list_tasks_in_sheet            │
│  → Gets available tasks: [TASK-001, ...] │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│  Agent reports to user:                 │
│  "Task TASK-999 not found.              │
│   Available: TASK-001, TASK-002, ..."   │
└─────────────────────────────────────────┘
```

### Error Handling Tasks

| Error | Agent Response |
|-------|---------------|
| Task not found | List available tasks |
| File not found | Search for similar files |
| Empty result | Broaden search pattern |
| Rate limited | Wait and retry |

---

## Agent Capabilities

### Tool Summary

| Tool | Agent | Purpose |
|------|-------|---------|
| `get_task_from_sheet` | Sheet | Fetch task by ID |
| `list_tasks_in_sheet` | Sheet/Manual | List all tasks (fallback) |
| `index_codebase` | Parser | Build file tree index |
| `read_file` | Parser/Reasoning/Verification | Read actual file content |
| `search_codebase` | Parser/Reasoning/Verification | Search for patterns |

### Agent Decision Making

**Parser Agent:**
```
1. Index codebase (uses cache if valid)
2. Analyze task description
3. Decide: need more info?
   → If yes: search_codebase for patterns
   → If yes: read_file for key files
4. Output: relevant files + summary
```

**Reasoning Agent:**
```
1. Read task details
2. Analyze codebase index
3. Decide: which files to read?
   → Read config files first
   → Read entry points
   → Read relevant modules
4. Plan steps based on actual code
5. Generate guide with real references
```

**Verification Agent:**
```
1. Read generated guide
2. Verify each file path exists
3. Check code references are accurate
4. If issues found:
   → Read the actual file to confirm
   → Annotate/improve guide
5. Output: verified guide
```

---

## Summary

The enhanced Onboard AI is now more **agentic** because:

1. **Dynamic Tool Usage**: Agents decide WHAT to read and search based on context
2. **Self-Correction**: Verification agent can improve the guide
3. **Error Handling**: Fallback to listing tasks when not found
4. **Caching**: Performance optimization for repeated runs
5. **Hybrid Approach**: Light index + selective file reading (better than full RAG for codebases)

This moves from a "linear pipeline" to a "multi-agent system with agency" - agents can make decisions, use tools dynamically, and self-correct.

