# Onboard AI

An agentic multi-agent system (powered by CrewAI) that helps new developers get up to speed on tasks in a codebase. Given a task from a Google Sheet, the system identifies which files to modify and produces a step-by-step guide.

## Architecture

Onboard AI uses a **multi-agent system** with 4 specialized agents:

| Agent | Role |
|-------|------|
| **Sheet Agent** | Fetches task details from Google Sheets by task ID |
| **Parser Agent** | Indexes codebase, finds relevant files for the task |
| **Reasoning Agent** | Plans implementation steps, reads relevant files, writes guides |
| **Verification Agent** | Reviews the guide for accuracy and completeness |

### How It Works

1. **Sheet Agent** fetches task details from Google Sheet (task_id, title, description, assignee)
2. **Parser Agent** scans the codebase and identifies files relevant to the task
3. **Reasoning Agent** reads the relevant files and generates a step-by-step guide
4. **Verification Agent** reviews and improves the guide

Each agent has access to tools:
- `get_task_from_sheet` - Fetch task from Google Sheet
- `list_tasks_in_sheet` - List all available tasks
- `index_codebase` - Scan and index codebase (with caching)
- `read_file` - Read specific file contents
- `search_codebase` - Search for patterns in code

## Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```

### Google Sheets API

1. Create a Google Cloud project and enable **Google Sheets API** (and Drive API if opening by URL).
2. Create a service account (APIs & Services → Credentials → Create credentials → Service account). Create a key (JSON) and download it.
3. Place the downloaded file as **`credentials.json`** in the **project root** (or in `config/credentials.json`, or set `GOOGLE_APPLICATION_CREDENTIALS` to its path).
4. **Share your Google Sheet** with the service account's email (e.g., `xxx@yyy.iam.gserviceaccount.com`) as Viewer.
5. Sheet should have a header row. Expected columns (case-insensitive): **Task ID**, **Assignee**, **Title**, **Description**, **Status**.

### Ollama (LLM)

```bash
# Install Ollama
brew install ollama  # macOS
# or: curl -fsSL https://ollama.com/install.sh | sh  # Linux

# Pull the model
ollama pull llama3
```

## Usage

### Basic Usage

```bash
# Run the crew with a task from Google Sheet
python -m src.crew --task-id TASK-001

# Or with explicit sheet URL
python -m src.crew --task-id TASK-001 --sheet "https://docs.google.com/spreadsheets/d/SHEET_ID/..."

# Specify a different codebase to analyze
python -m src.crew --task-id TASK-001 --codebase-root /path/to/project

# Enable verbose debug output
python -m src.crew --task-id TASK-001 --verbose
```

### Command Options

| Flag | Short | Description |
|------|-------|-------------|
| `--task-id` | `-t` | **Required.** Task ID from Google Sheet (e.g., TASK-001) |
| `--sheet` | `-s` | Google Sheet URL or key (default: configured default sheet) |
| `--codebase-root` | `-r` | Path to codebase to analyze (default: current directory) |
| `--model` | `-m` | Ollama model to use (default: llama3) |
| `--verbose` | `-v` | Enable verbose debug output |

## Project Layout

```
Onboard_AI/
├── src/
│   ├── crew/              # CrewAI multi-agent system (main entry point)
│   │   ├── __main__.py   # CLI entry: python -m src.crew
│   │   └── crew_main.py  # Agent definitions and crew orchestration
│   ├── parser/            # Phase 1: codebase scanner & index
│   │   ├── scanner.py    # Filesystem scanning
│   │   └── index_builder.py  # Index generation
│   ├── sheet_reader/      # Phase 2: Google Sheets integration
│   │   ├── reader.py     # Task reading logic
│   │   └── config.py     # Credentials configuration
│   ├── reasoning/         # (Legacy) Ollama-based reasoning
│   ├── orchestration/    # (Legacy) Pipeline orchestration
│   └── index_cache/       # Cached codebase indexes
├── docs/                  # Documentation
├── scripts/               # Utility scripts
├── requirements.txt
└── README.md
```

## Key Features

- **Caching**: Codebase indexes are cached to avoid repeated scans
- **Tool-Augmented Agents**: Agents can read files and search code
- **Deterministic Output**: Expected output formats enforce machine-readable results
- **Error Handling**: Graceful handling of missing tasks, files, etc.
- **Configurable**: Custom models, verbose output, different codebases

## Troubleshooting

### "credentials.json not found"

Ensure `credentials.json` is in:
- Project root, OR
- `config/credentials.json`, OR
- Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

### Ollama connection errors

Ensure Ollama is running:
```bash
ollama serve
```

### Task not found

Run with `--verbose` to see available task IDs:
```bash
python -m src.crew --task-id TASK-001 --verbose
```

## Development

The system uses:
- **CrewAI** - Multi-agent orchestration
- **Ollama (Llama3)** - Local LLM for reasoning
- **gspread** - Google Sheets API
- **Custom parser** - File scanning and indexing with pathspec

